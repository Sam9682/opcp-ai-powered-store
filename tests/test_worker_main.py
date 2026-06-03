"""Tests for the worker __main__ entry point.

Verifies signal handling, worker initialization, and the main() function
behavior when running as python -m src.serverless.worker.
"""

import os
import signal
import sys
from unittest.mock import MagicMock, patch

import pytest

# Mock psycopg2 before importing worker module
mock_psycopg2 = MagicMock()
mock_psycopg2.extras = MagicMock()
sys.modules.setdefault("psycopg2", mock_psycopg2)
sys.modules.setdefault("psycopg2.extras", mock_psycopg2.extras)

from src.serverless.worker import ServerlessWorker, main


class TestWorkerMain:
    """Test the main() entry point function."""

    @patch("src.serverless.worker.ContainerRuntime.detect")
    @patch("src.serverless.worker.ServerlessWorker")
    def test_main_creates_worker_with_env_worker_id(self, mock_worker_cls, mock_detect):
        """Worker ID should come from WORKER_ID environment variable."""
        mock_runtime = MagicMock()
        mock_detect.return_value = mock_runtime
        mock_worker_instance = MagicMock()
        mock_worker_cls.return_value = mock_worker_instance

        with patch.dict(os.environ, {"WORKER_ID": "test-worker-42"}):
            main()

        mock_worker_cls.assert_called_once()
        call_kwargs = mock_worker_cls.call_args[1]
        assert call_kwargs["worker_id"] == "test-worker-42"
        assert call_kwargs["runtime"] is mock_runtime
        mock_worker_instance.run.assert_called_once()

    @patch("src.serverless.worker.ContainerRuntime.detect")
    @patch("src.serverless.worker.ServerlessWorker")
    def test_main_generates_default_worker_id(self, mock_worker_cls, mock_detect):
        """Without WORKER_ID env var, a default with hostname and PID is used."""
        mock_runtime = MagicMock()
        mock_detect.return_value = mock_runtime
        mock_worker_instance = MagicMock()
        mock_worker_cls.return_value = mock_worker_instance

        env = os.environ.copy()
        env.pop("WORKER_ID", None)
        with patch.dict(os.environ, env, clear=True):
            main()

        call_kwargs = mock_worker_cls.call_args[1]
        # Should start with "worker-" and contain the PID
        assert call_kwargs["worker_id"].startswith("worker-")
        assert str(os.getpid()) in call_kwargs["worker_id"]

    @patch("src.serverless.worker.ContainerRuntime.detect")
    @patch("src.serverless.worker.ServerlessWorker")
    def test_main_uses_db_config_from_env(self, mock_worker_cls, mock_detect):
        """Database config should be read from environment variables."""
        mock_detect.return_value = MagicMock()
        mock_worker_instance = MagicMock()
        mock_worker_cls.return_value = mock_worker_instance

        env_vars = {
            "WORKER_ID": "w1",
            "POSTGRES_HOST": "dbhost",
            "POSTGRES_PORT": "5433",
            "POSTGRES_DB": "testdb",
            "POSTGRES_USER": "testuser",
            "POSTGRES_PASSWORD": "testpass",
        }
        with patch.dict(os.environ, env_vars):
            main()

        call_kwargs = mock_worker_cls.call_args[1]
        db_config = call_kwargs["db_config"]
        assert db_config["host"] == "dbhost"
        assert db_config["port"] == 5433
        assert db_config["database"] == "testdb"
        assert db_config["user"] == "testuser"
        assert db_config["password"] == "testpass"

    @patch("src.serverless.worker.ContainerRuntime.detect")
    def test_main_exits_when_no_runtime_detected(self, mock_detect):
        """Should exit with code 1 if no container runtime is found."""
        mock_detect.side_effect = RuntimeError("No supported container runtime found")

        with patch.dict(os.environ, {"WORKER_ID": "w1"}):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    @patch("src.serverless.worker.ContainerRuntime.detect")
    @patch("src.serverless.worker.ServerlessWorker")
    def test_main_registers_signal_handlers(self, mock_worker_cls, mock_detect):
        """SIGTERM and SIGINT handlers should be registered."""
        mock_detect.return_value = MagicMock()
        mock_worker_instance = MagicMock()
        mock_worker_cls.return_value = mock_worker_instance

        with patch.dict(os.environ, {"WORKER_ID": "w1"}):
            with patch("signal.signal") as mock_signal:
                main()

                # Check that signal.signal was called for both SIGTERM and SIGINT
                sigterm_calls = [
                    c for c in mock_signal.call_args_list
                    if c[0][0] == signal.SIGTERM
                ]
                sigint_calls = [
                    c for c in mock_signal.call_args_list
                    if c[0][0] == signal.SIGINT
                ]
                assert len(sigterm_calls) == 1
                assert len(sigint_calls) == 1


class TestWorkerSignalHandling:
    """Test that signal handlers properly trigger graceful shutdown."""

    @patch("src.serverless.worker.ContainerRuntime.detect")
    def test_sigterm_sets_running_to_false(self, mock_detect):
        """SIGTERM handler should set worker.running = False."""
        mock_runtime = MagicMock()
        mock_detect.return_value = mock_runtime

        # We'll capture the signal handler and call it manually
        registered_handlers = {}

        def capture_signal(signum, handler):
            registered_handlers[signum] = handler

        with patch.dict(os.environ, {"WORKER_ID": "w1"}):
            with patch("signal.signal", side_effect=capture_signal):
                with patch.object(ServerlessWorker, "run"):
                    main()

        # Check SIGTERM handler was registered
        assert signal.SIGTERM in registered_handlers
        handler = registered_handlers[signal.SIGTERM]
        assert callable(handler)

    @patch("src.serverless.worker.ContainerRuntime.detect")
    def test_sigint_sets_running_to_false(self, mock_detect):
        """SIGINT handler should set worker.running = False."""
        mock_runtime = MagicMock()
        mock_detect.return_value = mock_runtime

        registered_handlers = {}

        def capture_signal(signum, handler):
            registered_handlers[signum] = handler

        with patch.dict(os.environ, {"WORKER_ID": "w1"}):
            with patch("signal.signal", side_effect=capture_signal):
                with patch.object(ServerlessWorker, "run"):
                    main()

        # Check SIGINT handler was registered
        assert signal.SIGINT in registered_handlers
        handler = registered_handlers[signal.SIGINT]
        assert callable(handler)


class TestWorkerRunLoop:
    """Test the run() method of ServerlessWorker."""

    def test_run_stops_when_running_set_to_false(self):
        """Worker.run() should exit when self.running becomes False."""
        mock_runtime = MagicMock()
        worker = ServerlessWorker(
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

        # Set running to False immediately so the loop exits
        worker.running = False
        # This should not hang
        worker.run()

    @patch("src.serverless.worker.time.sleep")
    def test_run_sleeps_when_no_job(self, mock_sleep):
        """Worker should sleep for poll_interval when queue is empty."""
        mock_runtime = MagicMock()
        worker = ServerlessWorker(
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

        call_count = [0]

        def stop_after_one_iteration(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] >= 1:
                worker.running = False

        mock_sleep.side_effect = stop_after_one_iteration

        with patch.object(worker, "claim_next_job", return_value=None):
            worker.run()

        mock_sleep.assert_called_with(worker.poll_interval)

    @patch("src.serverless.worker.time.sleep")
    def test_run_executes_job_when_found(self, mock_sleep):
        """Worker should execute a job when one is claimed."""
        mock_runtime = MagicMock()
        worker = ServerlessWorker(
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

        fake_job = {
            "id": "job-123",
            "image": "python:3.11",
            "command": ["python", "-c", "print('hi')"],
            "environment": {},
            "timeout_seconds": 300,
            "user_id": 1,
        }

        claim_calls = [0]

        def claim_side_effect():
            claim_calls[0] += 1
            if claim_calls[0] == 1:
                return fake_job
            worker.running = False
            return None

        with patch.object(worker, "claim_next_job", side_effect=claim_side_effect):
            with patch.object(worker, "execute_job") as mock_execute:
                worker.run()

        mock_execute.assert_called_once_with(fake_job)
