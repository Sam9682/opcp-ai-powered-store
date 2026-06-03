"""Tests for the serverless log cleanup module.

Verifies that cleanup_old_logs correctly deletes old log entries and
terminal-state jobs, and that the worker integration triggers cleanup
on the daily schedule.
"""

import sys
import time
from unittest.mock import MagicMock, call, patch

import pytest

# Mock psycopg2 before importing modules under test
mock_psycopg2 = MagicMock()
mock_psycopg2.extras = MagicMock()
sys.modules.setdefault("psycopg2", mock_psycopg2)
sys.modules.setdefault("psycopg2.extras", mock_psycopg2.extras)

from src.serverless.log_cleanup import cleanup_old_logs
from src.serverless.worker import ServerlessWorker


DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "testdb",
    "user": "testuser",
    "password": "testpass",
}


class TestCleanupOldLogs:
    """Tests for the cleanup_old_logs function."""

    def test_deletes_old_logs_and_jobs(self):
        """Should execute DELETE queries and return deletion counts."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        # First execute returns 5 logs deleted, second returns 3 jobs deleted
        mock_cursor.rowcount = 5
        mock_conn.cursor.return_value = mock_cursor

        def rowcount_side_effect(*args):
            # Track call count to return different rowcounts
            pass

        # We need to handle sequential rowcount reads
        type(mock_cursor).rowcount = property(
            lambda self: rowcount_side_effect_tracker.pop(0)
        )

        class RowcountTracker:
            def __init__(self, values):
                self._values = list(values)

            def pop(self, idx):
                return self._values.pop(idx)

        rowcount_side_effect_tracker = RowcountTracker([5, 3])

        with patch("src.serverless.log_cleanup.psycopg2.connect", return_value=mock_conn):
            logs_deleted, jobs_deleted = cleanup_old_logs(DB_CONFIG)

        assert logs_deleted == 5
        assert jobs_deleted == 3
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_connects_with_correct_parameters(self):
        """Should pass db_config values to psycopg2.connect."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.rowcount = 0
        mock_conn.cursor.return_value = mock_cursor

        with patch("src.serverless.log_cleanup.psycopg2.connect", return_value=mock_conn) as mock_connect:
            cleanup_old_logs(DB_CONFIG)

        mock_connect.assert_called_once_with(
            host="localhost",
            port=5432,
            dbname="testdb",
            user="testuser",
            password="testpass",
        )

    def test_executes_correct_sql_queries(self):
        """Should execute DELETE queries for logs and jobs with correct SQL."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.rowcount = 0
        mock_conn.cursor.return_value = mock_cursor

        with patch("src.serverless.log_cleanup.psycopg2.connect", return_value=mock_conn):
            cleanup_old_logs(DB_CONFIG)

        # Should have executed two DELETE statements
        assert mock_cursor.execute.call_count == 2

        # First call: delete old logs
        first_sql = mock_cursor.execute.call_args_list[0][0][0]
        assert "DELETE FROM serverless_job_logs" in first_sql
        assert "INTERVAL '30 days'" in first_sql

        # Second call: delete old terminal jobs
        second_sql = mock_cursor.execute.call_args_list[1][0][0]
        assert "DELETE FROM serverless_jobs" in second_sql
        assert "INTERVAL '30 days'" in second_sql
        assert "completed" in second_sql
        assert "failed" in second_sql
        assert "timeout" in second_sql
        assert "cancelled" in second_sql

    def test_rolls_back_on_error(self):
        """Should rollback and re-raise on database errors."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.execute.side_effect = Exception("DB error")
        mock_conn.cursor.return_value = mock_cursor

        with patch("src.serverless.log_cleanup.psycopg2.connect", return_value=mock_conn):
            with pytest.raises(Exception, match="DB error"):
                cleanup_old_logs(DB_CONFIG)

        mock_conn.rollback.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_closes_connection_on_success(self):
        """Should close the connection after successful cleanup."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.rowcount = 0
        mock_conn.cursor.return_value = mock_cursor

        with patch("src.serverless.log_cleanup.psycopg2.connect", return_value=mock_conn):
            cleanup_old_logs(DB_CONFIG)

        mock_conn.close.assert_called_once()

    def test_returns_zero_counts_when_nothing_to_delete(self):
        """Should return (0, 0) when no old records exist."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.rowcount = 0
        mock_conn.cursor.return_value = mock_cursor

        with patch("src.serverless.log_cleanup.psycopg2.connect", return_value=mock_conn):
            logs_deleted, jobs_deleted = cleanup_old_logs(DB_CONFIG)

        assert logs_deleted == 0
        assert jobs_deleted == 0


class TestWorkerCleanupIntegration:
    """Tests for the cleanup integration in the worker's run loop."""

    def _make_worker(self):
        """Helper to create a worker instance for testing."""
        return ServerlessWorker(
            worker_id="test-worker",
            runtime=MagicMock(),
            db_config=DB_CONFIG,
        )

    def test_worker_has_cleanup_attributes(self):
        """Worker should have last_cleanup_time and cleanup_interval attrs."""
        worker = self._make_worker()
        assert hasattr(worker, "last_cleanup_time")
        assert hasattr(worker, "cleanup_interval")
        assert worker.last_cleanup_time == 0.0
        assert worker.cleanup_interval == 86400.0

    def test_cleanup_runs_on_first_iteration(self):
        """Cleanup should run on the first loop iteration (last_cleanup_time=0)."""
        worker = self._make_worker()

        with patch("src.serverless.worker.cleanup_old_logs", return_value=(0, 0)) as mock_cleanup:
            with patch.object(worker, "claim_next_job", return_value=None):
                with patch("src.serverless.worker.time.sleep", side_effect=lambda _: setattr(worker, 'running', False)):
                    worker.run()

        mock_cleanup.assert_called_once_with(DB_CONFIG)

    def test_cleanup_does_not_run_within_interval(self):
        """Cleanup should not run again if interval has not elapsed."""
        worker = self._make_worker()
        # Set last_cleanup_time to now so interval hasn't elapsed
        worker.last_cleanup_time = time.time()

        with patch("src.serverless.worker.cleanup_old_logs") as mock_cleanup:
            with patch.object(worker, "claim_next_job", return_value=None):
                with patch("src.serverless.worker.time.sleep", side_effect=lambda _: setattr(worker, 'running', False)):
                    worker.run()

        mock_cleanup.assert_not_called()

    def test_cleanup_failure_does_not_stop_worker(self):
        """If cleanup fails, the worker should continue running."""
        worker = self._make_worker()

        with patch("src.serverless.worker.cleanup_old_logs", side_effect=Exception("cleanup failed")):
            with patch.object(worker, "claim_next_job", return_value=None):
                with patch("src.serverless.worker.time.sleep", side_effect=lambda _: setattr(worker, 'running', False)):
                    # Should not raise
                    worker.run()

    def test_cleanup_updates_last_cleanup_time(self):
        """After running cleanup, last_cleanup_time should be updated."""
        worker = self._make_worker()
        assert worker.last_cleanup_time == 0.0

        with patch("src.serverless.worker.cleanup_old_logs", return_value=(0, 0)):
            with patch.object(worker, "claim_next_job", return_value=None):
                with patch("src.serverless.worker.time.sleep", side_effect=lambda _: setattr(worker, 'running', False)):
                    worker.run()

        assert worker.last_cleanup_time > 0.0

    def test_cleanup_updates_time_even_on_failure(self):
        """last_cleanup_time should update even if cleanup raises, to avoid retry storm."""
        worker = self._make_worker()

        with patch("src.serverless.worker.cleanup_old_logs", side_effect=Exception("DB down")):
            with patch.object(worker, "claim_next_job", return_value=None):
                with patch("src.serverless.worker.time.sleep", side_effect=lambda _: setattr(worker, 'running', False)):
                    worker.run()

        # Should be updated to prevent rapid retries
        assert worker.last_cleanup_time > 0.0
