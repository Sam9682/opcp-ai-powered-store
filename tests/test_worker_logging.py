"""Tests for worker structured logging configuration.

Verifies that the worker sets up RotatingFileHandler and StreamHandler,
logs to the correct file, and emits structured messages for job lifecycle
events.
"""

import logging
import logging.handlers
import os
import sys
import time
from unittest.mock import MagicMock, patch

import pytest

# Mock psycopg2 before importing worker module
mock_psycopg2 = MagicMock()
mock_psycopg2.extras = MagicMock()
sys.modules.setdefault("psycopg2", mock_psycopg2)
sys.modules.setdefault("psycopg2.extras", mock_psycopg2.extras)

from src.serverless.worker import ServerlessWorker, main


class TestWorkerLoggingSetup:
    """Test that main() configures logging with RotatingFileHandler."""

    @patch("src.serverless.worker.ContainerRuntime.detect")
    @patch("src.serverless.worker.ServerlessWorker")
    def test_main_creates_rotating_file_handler(self, mock_worker_cls, mock_detect):
        """main() should configure a RotatingFileHandler on the serverless logger."""
        mock_detect.return_value = MagicMock()
        mock_worker_cls.return_value = MagicMock()

        with patch.dict(os.environ, {"WORKER_ID": "w1"}):
            main()

        serverless_logger = logging.getLogger("src.serverless")
        handler_types = [type(h) for h in serverless_logger.handlers]
        assert logging.handlers.RotatingFileHandler in handler_types

    @patch("src.serverless.worker.ContainerRuntime.detect")
    @patch("src.serverless.worker.ServerlessWorker")
    def test_main_creates_stream_handler(self, mock_worker_cls, mock_detect):
        """main() should configure a StreamHandler on the serverless logger."""
        mock_detect.return_value = MagicMock()
        mock_worker_cls.return_value = MagicMock()

        with patch.dict(os.environ, {"WORKER_ID": "w1"}):
            main()

        serverless_logger = logging.getLogger("src.serverless")
        handler_types = [type(h) for h in serverless_logger.handlers]
        assert logging.StreamHandler in handler_types

    @patch("src.serverless.worker.ContainerRuntime.detect")
    @patch("src.serverless.worker.ServerlessWorker")
    def test_rotating_handler_has_correct_max_bytes(self, mock_worker_cls, mock_detect):
        """RotatingFileHandler should be configured with 10 MB max file size."""
        mock_detect.return_value = MagicMock()
        mock_worker_cls.return_value = MagicMock()

        with patch.dict(os.environ, {"WORKER_ID": "w1"}):
            main()

        serverless_logger = logging.getLogger("src.serverless")
        rotating_handlers = [
            h for h in serverless_logger.handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)
        ]
        assert len(rotating_handlers) == 1
        assert rotating_handlers[0].maxBytes == 10 * 1024 * 1024

    @patch("src.serverless.worker.ContainerRuntime.detect")
    @patch("src.serverless.worker.ServerlessWorker")
    def test_rotating_handler_has_correct_backup_count(self, mock_worker_cls, mock_detect):
        """RotatingFileHandler should keep 5 backup files."""
        mock_detect.return_value = MagicMock()
        mock_worker_cls.return_value = MagicMock()

        with patch.dict(os.environ, {"WORKER_ID": "w1"}):
            main()

        serverless_logger = logging.getLogger("src.serverless")
        rotating_handlers = [
            h for h in serverless_logger.handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)
        ]
        assert len(rotating_handlers) == 1
        assert rotating_handlers[0].backupCount == 5

    @patch("src.serverless.worker.ContainerRuntime.detect")
    @patch("src.serverless.worker.ServerlessWorker")
    def test_log_file_path_contains_serverless_worker(self, mock_worker_cls, mock_detect):
        """Log file should be at logs/serverless_worker.log."""
        mock_detect.return_value = MagicMock()
        mock_worker_cls.return_value = MagicMock()

        with patch.dict(os.environ, {"WORKER_ID": "w1"}):
            main()

        serverless_logger = logging.getLogger("src.serverless")
        rotating_handlers = [
            h for h in serverless_logger.handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)
        ]
        assert len(rotating_handlers) == 1
        log_path = rotating_handlers[0].baseFilename
        assert log_path.endswith("serverless_worker.log")
        assert "logs" in log_path

    @patch("src.serverless.worker.ContainerRuntime.detect")
    @patch("src.serverless.worker.ServerlessWorker")
    def test_log_format_includes_timestamp(self, mock_worker_cls, mock_detect):
        """Log formatter should include asctime, name, levelname, and message."""
        mock_detect.return_value = MagicMock()
        mock_worker_cls.return_value = MagicMock()

        with patch.dict(os.environ, {"WORKER_ID": "w1"}):
            main()

        serverless_logger = logging.getLogger("src.serverless")
        for handler in serverless_logger.handlers:
            fmt = handler.formatter._fmt
            assert "%(asctime)s" in fmt
            assert "%(name)s" in fmt
            assert "%(levelname)s" in fmt
            assert "%(message)s" in fmt


class TestWorkerLogMessages:
    """Test that worker methods emit expected log messages."""

    def _make_worker(self):
        """Create a worker instance with mocked runtime."""
        mock_runtime = MagicMock()
        return ServerlessWorker(
            worker_id="test-worker",
            runtime=mock_runtime,
            db_config={
                "host": "localhost",
                "port": 5432,
                "database": "test",
                "user": "user",
                "password": "pass",
            },
        )

    @pytest.fixture(autouse=True)
    def _enable_propagation(self):
        """Ensure logger propagation is enabled so caplog captures messages."""
        worker_logger = logging.getLogger("src.serverless.worker")
        parent_logger = logging.getLogger("src.serverless")
        old_propagate_worker = worker_logger.propagate
        old_propagate_parent = parent_logger.propagate
        worker_logger.propagate = True
        parent_logger.propagate = True
        yield
        worker_logger.propagate = old_propagate_worker
        parent_logger.propagate = old_propagate_parent

    def test_execute_job_logs_start(self, caplog):
        """execute_job should log execution start with job_id, image, command."""
        worker = self._make_worker()
        worker.runtime.pull_image.side_effect = Exception("test pull fail")

        job = {
            "id": "job-abc",
            "image": "python:3.11",
            "command": ["python", "-c", "print('hello')"],
            "environment": {},
            "timeout_seconds": 60,
            "user_id": 1,
        }

        with caplog.at_level(logging.INFO, logger="src.serverless.worker"):
            worker.execute_job(job)

        start_msgs = [r for r in caplog.records if "Execution start" in r.message]
        assert len(start_msgs) >= 1
        assert "job-abc" in start_msgs[0].message
        assert "python:3.11" in start_msgs[0].message

    def test_execute_job_logs_failure_with_duration(self, caplog):
        """execute_job should log execution end with status=failed and duration."""
        worker = self._make_worker()
        worker.runtime.pull_image.side_effect = Exception("pull failed")

        job = {
            "id": "job-fail",
            "image": "python:3.11",
            "command": ["python", "bad.py"],
            "environment": {},
            "timeout_seconds": 60,
            "user_id": 1,
        }

        with patch.object(worker, "mark_failed"):
            with caplog.at_level(logging.ERROR, logger="src.serverless.worker"):
                worker.execute_job(job)

        end_msgs = [r for r in caplog.records if "Execution end" in r.message and "failed" in r.message]
        assert len(end_msgs) >= 1
        assert "duration" in end_msgs[0].message

    def test_execute_job_logs_timeout(self, caplog):
        """execute_job should log timeout events with duration."""
        worker = self._make_worker()
        worker.runtime.pull_image.return_value = None
        worker.runtime.run_container.return_value = "container-123"
        worker.runtime.wait.side_effect = TimeoutError("timed out")

        job = {
            "id": "job-timeout",
            "image": "python:3.11",
            "command": ["sleep", "9999"],
            "environment": {},
            "timeout_seconds": 1,
            "user_id": 1,
        }

        with patch.object(worker, "mark_timeout"):
            with patch.object(worker, "check_cancelled", return_value=False):
                with caplog.at_level(logging.WARNING, logger="src.serverless.worker"):
                    worker.execute_job(job)

        timeout_msgs = [r for r in caplog.records if "timeout" in r.message.lower() and "Execution end" in r.message]
        assert len(timeout_msgs) >= 1
        assert "duration" in timeout_msgs[0].message

    def test_run_logs_startup_and_shutdown(self, caplog):
        """run() should log worker startup and graceful shutdown."""
        worker = self._make_worker()
        worker.running = False  # Immediately stop

        with caplog.at_level(logging.INFO, logger="src.serverless.worker"):
            worker.run()

        messages = [r.message for r in caplog.records]
        start_msgs = [m for m in messages if "starting main loop" in m]
        shutdown_msgs = [m for m in messages if "shutting down gracefully" in m]
        assert len(start_msgs) >= 1
        assert len(shutdown_msgs) >= 1
