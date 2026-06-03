"""Tests for ServerlessWorker: job claiming, execution lifecycle, timeout, cancellation.

Verifies the core worker behavior:
- Job claiming with FOR UPDATE SKIP LOCKED pattern
- Full job execution lifecycle (pull, run, wait, logs, store, complete)
- Timeout handling (container stop + status update)
- Cancellation detection during execution
"""

import sys
from unittest.mock import MagicMock, call, patch

import pytest

# Mock psycopg2 before importing worker module
mock_psycopg2 = MagicMock()
mock_psycopg2.extras = MagicMock()
sys.modules.setdefault("psycopg2", mock_psycopg2)
sys.modules.setdefault("psycopg2.extras", mock_psycopg2.extras)

from src.serverless.worker import CancellationError, ServerlessWorker


@pytest.fixture
def db_config():
    return {
        "host": "localhost",
        "port": 5432,
        "database": "testdb",
        "user": "testuser",
        "password": "testpass",
    }


@pytest.fixture
def worker(db_config):
    runtime = MagicMock()
    w = ServerlessWorker(
        worker_id="worker-test-1",
        runtime=runtime,
        db_config=db_config,
        registry_whitelist=["docker.io", "ghcr.io"],
    )
    return w


@pytest.fixture
def sample_job():
    return {
        "id": "job-uuid-123",
        "user_id": 1,
        "image": "docker.io/python:3.11",
        "command": ["python", "-c", "print('hello')"],
        "environment": {"KEY": "value"},
        "timeout_seconds": 300,
    }


# =============================================================================
# Job Claiming with FOR UPDATE SKIP LOCKED
# =============================================================================


class TestClaimNextJob:
    """Tests for claim_next_job using the FOR UPDATE SKIP LOCKED pattern."""

    @patch("psycopg2.connect")
    def test_returns_none_when_queue_is_empty(self, mock_connect, worker):
        """claim_next_job returns None when no pending jobs exist."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchone.return_value = None

        result = worker.claim_next_job()

        assert result is None
        mock_conn.commit.assert_called()

    @patch("psycopg2.connect")
    def test_returns_job_dict_when_pending_job_exists(self, mock_connect, worker):
        """claim_next_job returns a job dictionary when a pending job is found."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Simulate a row returned from the SELECT
        mock_cursor.fetchone.return_value = {
            "id": "job-uuid-456",
            "user_id": 2,
            "image": "ghcr.io/org/app:latest",
            "command": ["./run.sh"],
            "environment": {"ENV": "prod"},
            "timeout_seconds": 600,
        }

        result = worker.claim_next_job()

        assert result is not None
        assert result["id"] == "job-uuid-456"
        assert result["image"] == "ghcr.io/org/app:latest"
        assert result["command"] == ["./run.sh"]
        assert result["environment"] == {"ENV": "prod"}
        assert result["timeout_seconds"] == 600
        assert result["user_id"] == 2

    @patch("psycopg2.connect")
    def test_uses_for_update_skip_locked_in_sql(self, mock_connect, worker):
        """claim_next_job SQL must include FOR UPDATE SKIP LOCKED."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchone.return_value = None

        worker.claim_next_job()

        # Get the SQL from the first execute call
        select_call = mock_cursor.execute.call_args_list[0]
        sql = select_call[0][0]
        assert "FOR UPDATE SKIP LOCKED" in sql

    @patch("psycopg2.connect")
    def test_updates_status_to_running_and_sets_worker_id(self, mock_connect, worker):
        """After claiming, job status is updated to 'running' with this worker's ID."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        mock_cursor.fetchone.return_value = {
            "id": "job-uuid-789",
            "user_id": 1,
            "image": "docker.io/alpine:latest",
            "command": ["echo", "hi"],
            "environment": {},
            "timeout_seconds": 60,
        }

        worker.claim_next_job()

        # The second execute call should be the UPDATE
        update_call = mock_cursor.execute.call_args_list[1]
        update_sql = update_call[0][0]
        update_params = update_call[0][1]

        assert "status = 'running'" in update_sql
        assert "worker_id" in update_sql
        assert update_params == ("worker-test-1", "job-uuid-789")


# =============================================================================
# Job Execution Lifecycle
# =============================================================================


class TestExecuteJob:
    """Tests for the full execute_job lifecycle."""

    @patch("psycopg2.connect")
    def test_full_execution_lifecycle(self, mock_connect, worker, sample_job):
        """execute_job calls pull_image, run_container, wait, get_logs, store_result, mark_completed."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        runtime = worker.runtime
        runtime.run_container.return_value = "container-abc"
        runtime.get_logs.side_effect = lambda cid, stream: (
            "hello\n" if stream == "stdout" else ""
        )

        # Make _wait_with_cancellation_check return exit code 0
        with patch.object(worker, "_wait_with_cancellation_check", return_value=0):
            with patch.object(worker, "store_result") as mock_store:
                with patch.object(worker, "mark_completed") as mock_mark:
                    worker.execute_job(sample_job)

        runtime.pull_image.assert_called_once_with("docker.io/python:3.11")
        runtime.run_container.assert_called_once()
        runtime.get_logs.assert_any_call("container-abc", stream="stdout")
        runtime.get_logs.assert_any_call("container-abc", stream="stderr")
        mock_store.assert_called_once_with("job-uuid-123", 0, "hello\n", "")
        mock_mark.assert_called_once_with("job-uuid-123", 0)
        runtime.cleanup.assert_called_once_with("container-abc")

    @patch("psycopg2.connect")
    def test_validates_registry_whitelist_before_execution(
        self, mock_connect, worker
    ):
        """execute_job rejects images not in the registry whitelist."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        job = {
            "id": "job-blocked",
            "user_id": 1,
            "image": "evil-registry.com/malware:latest",
            "command": ["./exploit"],
            "environment": {},
            "timeout_seconds": 60,
        }

        with patch.object(worker, "mark_failed") as mock_failed:
            worker.execute_job(job)

        mock_failed.assert_called_once()
        assert "whitelist" in mock_failed.call_args[0][1].lower() or \
               "whitelist" in mock_failed.call_args[0][1]
        # Runtime methods should NOT be called
        worker.runtime.pull_image.assert_not_called()
        worker.runtime.run_container.assert_not_called()

    @patch("psycopg2.connect")
    def test_marks_job_as_failed_on_runtime_error(self, mock_connect, worker, sample_job):
        """execute_job marks job as failed when the runtime raises an exception."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        worker.runtime.pull_image.side_effect = RuntimeError("Image pull failed")

        with patch.object(worker, "mark_failed") as mock_failed:
            worker.execute_job(sample_job)

        mock_failed.assert_called_once()
        assert "Image pull failed" in mock_failed.call_args[0][1]


# =============================================================================
# Timeout Handling
# =============================================================================


class TestTimeoutHandling:
    """Tests for timeout behavior during job execution."""

    @patch("psycopg2.connect")
    def test_marks_job_as_timeout_when_container_exceeds_timeout(
        self, mock_connect, worker, sample_job
    ):
        """execute_job marks job status as 'timeout' when TimeoutError is raised."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        worker.runtime.run_container.return_value = "container-timeout"

        with patch.object(
            worker,
            "_wait_with_cancellation_check",
            side_effect=TimeoutError("Container did not finish within 300 seconds"),
        ):
            with patch.object(worker, "mark_timeout") as mock_timeout:
                worker.execute_job(sample_job)

        mock_timeout.assert_called_once_with("job-uuid-123")

    @patch("psycopg2.connect")
    def test_stops_container_on_timeout(self, mock_connect, worker, sample_job):
        """execute_job stops the container when it exceeds its timeout."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        worker.runtime.run_container.return_value = "container-timeout"

        with patch.object(
            worker,
            "_wait_with_cancellation_check",
            side_effect=TimeoutError("timeout"),
        ):
            with patch.object(worker, "mark_timeout"):
                worker.execute_job(sample_job)

        worker.runtime.stop_container.assert_called_once_with(
            "container-timeout", timeout=10
        )


# =============================================================================
# Cancellation Handling
# =============================================================================


class TestCancellationHandling:
    """Tests for cancellation detection during job execution."""

    @patch("psycopg2.connect")
    def test_wait_with_cancellation_check_detects_cancelled_and_stops_container(
        self, mock_connect, worker
    ):
        """_wait_with_cancellation_check raises CancellationError when job is cancelled."""
        # First call to runtime.wait raises TimeoutError (container still running)
        worker.runtime.wait.side_effect = TimeoutError("still running")

        # check_cancelled returns True (job was cancelled)
        with patch.object(worker, "check_cancelled", return_value=True):
            with pytest.raises(CancellationError):
                worker._wait_with_cancellation_check(
                    container_id="container-cancel",
                    job_id="job-cancel-1",
                    timeout=60,
                )

        worker.runtime.stop_container.assert_called_once_with(
            "container-cancel", timeout=10
        )

    @patch("psycopg2.connect")
    def test_check_cancelled_returns_true_when_status_is_cancelled(
        self, mock_connect, worker
    ):
        """check_cancelled returns True when the job status in DB is 'cancelled'."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchone.return_value = ("cancelled",)

        result = worker.check_cancelled("job-cancel-2")

        assert result is True

    @patch("psycopg2.connect")
    def test_check_cancelled_returns_false_when_status_is_running(
        self, mock_connect, worker
    ):
        """check_cancelled returns False when the job is still running."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchone.return_value = ("running",)

        result = worker.check_cancelled("job-running-1")

        assert result is False
