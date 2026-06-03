"""Tests for the DockerRuntime and PodmanRuntime container runtime implementations.

Verifies Docker/Podman CLI command construction with security flags,
error handling, and timeout behavior.
"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from src.serverless.container_runtime import ContainerRuntime, DockerRuntime, PodmanRuntime


class TestDockerRuntimeInheritance:
    """Test that DockerRuntime properly inherits from ContainerRuntime."""

    def test_is_instance_of_container_runtime(self):
        rt = DockerRuntime()
        assert isinstance(rt, ContainerRuntime)

    def test_implements_all_abstract_methods(self):
        # Should not raise TypeError on instantiation
        rt = DockerRuntime()
        assert callable(rt.pull_image)
        assert callable(rt.run_container)
        assert callable(rt.stop_container)
        assert callable(rt.get_logs)
        assert callable(rt.wait)
        assert callable(rt.cleanup)


class TestDockerRuntimePullImage:
    """Test pull_image method."""

    @patch("src.serverless.container_runtime.subprocess.run")
    def test_pull_image_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        rt = DockerRuntime()
        rt.pull_image("python:3.11")
        mock_run.assert_called_once_with(
            ["docker", "pull", "python:3.11"],
            capture_output=True,
            text=True,
        )

    @patch("src.serverless.container_runtime.subprocess.run")
    def test_pull_image_failure_raises_runtime_error(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="not found"
        )
        rt = DockerRuntime()
        with pytest.raises(RuntimeError, match="Failed to pull image"):
            rt.pull_image("nonexistent:latest")


class TestDockerRuntimeRunContainer:
    """Test run_container method with security flags."""

    @patch("src.serverless.container_runtime.uuid.uuid4")
    @patch("src.serverless.container_runtime.subprocess.run")
    def test_run_container_includes_all_security_flags(self, mock_run, mock_uuid):
        mock_uuid.return_value = "test-uuid-1234"
        mock_run.return_value = MagicMock(
            returncode=0, stdout="abc123containerid\n", stderr=""
        )
        rt = DockerRuntime()
        container_id = rt.run_container(
            image="python:3.11",
            command=["python", "script.py"],
            env={"KEY": "value"},
            timeout=300,
        )

        cmd = mock_run.call_args[0][0]
        # Verify detached mode
        assert "-d" in cmd
        # Verify container name with UUID
        assert "--name" in cmd
        assert "job-test-uuid-1234" in cmd
        # Verify ALL security flags
        assert "--read-only" in cmd
        assert "--user" in cmd
        assert "nobody" in cmd
        assert "--cap-drop" in cmd
        assert "ALL" in cmd
        assert "--memory" in cmd
        assert "512m" in cmd
        assert "--cpus" in cmd
        assert "1" in cmd
        assert "--network" in cmd
        assert "none" in cmd
        assert "--security-opt" in cmd
        assert "no-new-privileges" in cmd
        assert "--pids-limit" in cmd
        assert "256" in cmd
        # Verify env
        assert "-e" in cmd
        assert "KEY=value" in cmd
        # Verify image and command at end
        assert cmd[-3] == "python:3.11"
        assert cmd[-2] == "python"
        assert cmd[-1] == "script.py"
        # Verify returned container ID is stripped
        assert container_id == "abc123containerid"

    @patch("src.serverless.container_runtime.uuid.uuid4")
    @patch("src.serverless.container_runtime.subprocess.run")
    def test_run_container_custom_resource_limits(self, mock_run, mock_uuid):
        mock_uuid.return_value = "test-uuid"
        mock_run.return_value = MagicMock(returncode=0, stdout="cid\n", stderr="")
        rt = DockerRuntime()
        rt.run_container(
            image="alpine:latest",
            command=["echo", "hello"],
            env={},
            timeout=60,
            memory_limit="1g",
            cpu_limit="2",
            network="bridge",
        )

        cmd = mock_run.call_args[0][0]
        assert "1g" in cmd
        assert "2" in cmd
        assert "bridge" in cmd

    @patch("src.serverless.container_runtime.uuid.uuid4")
    @patch("src.serverless.container_runtime.subprocess.run")
    def test_run_container_failure_raises_runtime_error(self, mock_run, mock_uuid):
        mock_uuid.return_value = "test-uuid"
        mock_run.return_value = MagicMock(
            returncode=125, stdout="", stderr="container failed to start"
        )
        rt = DockerRuntime()
        with pytest.raises(RuntimeError, match="Failed to start container"):
            rt.run_container(
                image="bad:image",
                command=["cmd"],
                env={},
                timeout=10,
            )


class TestDockerRuntimeStopContainer:
    """Test stop_container method."""

    @patch("src.serverless.container_runtime.subprocess.run")
    def test_stop_container_with_timeout(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        rt = DockerRuntime()
        rt.stop_container("abc123", timeout=15)
        mock_run.assert_called_once_with(
            ["docker", "stop", "-t", "15", "abc123"],
            capture_output=True,
            text=True,
        )

    @patch("src.serverless.container_runtime.subprocess.run")
    def test_stop_container_default_timeout(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        rt = DockerRuntime()
        rt.stop_container("abc123")
        mock_run.assert_called_once_with(
            ["docker", "stop", "-t", "10", "abc123"],
            capture_output=True,
            text=True,
        )

    @patch("src.serverless.container_runtime.subprocess.run")
    def test_stop_container_failure_raises_runtime_error(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="no such container"
        )
        rt = DockerRuntime()
        with pytest.raises(RuntimeError, match="Failed to stop container"):
            rt.stop_container("nonexistent")


class TestDockerRuntimeGetLogs:
    """Test get_logs method."""

    @patch("src.serverless.container_runtime.subprocess.run")
    def test_get_logs_stdout(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="hello world\n", stderr=""
        )
        rt = DockerRuntime()
        output = rt.get_logs("abc123", stream="stdout")
        assert output == "hello world\n"
        cmd = mock_run.call_args[0][0]
        assert "--stdout" in cmd
        assert "abc123" in cmd

    @patch("src.serverless.container_runtime.subprocess.run")
    def test_get_logs_stderr(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="", stderr="error msg\n"
        )
        rt = DockerRuntime()
        output = rt.get_logs("abc123", stream="stderr")
        assert output == "error msg\n"
        cmd = mock_run.call_args[0][0]
        assert "--stderr" in cmd


class TestDockerRuntimeWait:
    """Test wait method."""

    @patch("src.serverless.container_runtime.subprocess.run")
    def test_wait_returns_exit_code(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="0\n", stderr="")
        rt = DockerRuntime()
        exit_code = rt.wait("abc123", timeout=300)
        assert exit_code == 0
        mock_run.assert_called_once_with(
            ["docker", "wait", "abc123"],
            capture_output=True,
            text=True,
            timeout=300,
        )

    @patch("src.serverless.container_runtime.subprocess.run")
    def test_wait_nonzero_exit_code(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="1\n", stderr="")
        rt = DockerRuntime()
        exit_code = rt.wait("abc123", timeout=300)
        assert exit_code == 1

    @patch("src.serverless.container_runtime.subprocess.run")
    def test_wait_timeout_raises_timeout_error(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="docker wait", timeout=10)
        rt = DockerRuntime()
        with pytest.raises(TimeoutError, match="did not finish within"):
            rt.wait("abc123", timeout=10)

    @patch("src.serverless.container_runtime.subprocess.run")
    def test_wait_failure_raises_runtime_error(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="error waiting"
        )
        rt = DockerRuntime()
        with pytest.raises(RuntimeError, match="Failed to wait on container"):
            rt.wait("abc123", timeout=300)


class TestDockerRuntimeCleanup:
    """Test cleanup method."""

    @patch("src.serverless.container_runtime.subprocess.run")
    def test_cleanup_force_removes_container(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        rt = DockerRuntime()
        rt.cleanup("abc123")
        mock_run.assert_called_once_with(
            ["docker", "rm", "-f", "abc123"],
            capture_output=True,
            text=True,
        )

    @patch("src.serverless.container_runtime.subprocess.run")
    def test_cleanup_does_not_raise_on_failure(self, mock_run):
        # cleanup should not raise even if container doesn't exist
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="no such container"
        )
        rt = DockerRuntime()
        # Should not raise
        rt.cleanup("nonexistent")


class TestPodmanRuntimeInheritance:
    """Test that PodmanRuntime inherits from DockerRuntime and ContainerRuntime."""

    def test_is_instance_of_container_runtime(self):
        rt = PodmanRuntime()
        assert isinstance(rt, ContainerRuntime)

    def test_is_instance_of_docker_runtime(self):
        rt = PodmanRuntime()
        assert isinstance(rt, DockerRuntime)

    def test_uses_podman_binary(self):
        rt = PodmanRuntime()
        assert rt._binary == "podman"

    def test_docker_runtime_uses_docker_binary(self):
        rt = DockerRuntime()
        assert rt._binary == "docker"


class TestPodmanRuntimeCommands:
    """Test that PodmanRuntime uses 'podman' binary in all subprocess calls."""

    @patch("src.serverless.container_runtime.subprocess.run")
    def test_pull_image_uses_podman(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        rt = PodmanRuntime()
        rt.pull_image("python:3.11")
        mock_run.assert_called_once_with(
            ["podman", "pull", "python:3.11"],
            capture_output=True,
            text=True,
        )

    @patch("src.serverless.container_runtime.uuid.uuid4")
    @patch("src.serverless.container_runtime.subprocess.run")
    def test_run_container_uses_podman(self, mock_run, mock_uuid):
        mock_uuid.return_value = "test-uuid-podman"
        mock_run.return_value = MagicMock(
            returncode=0, stdout="podman-container-id\n", stderr=""
        )
        rt = PodmanRuntime()
        container_id = rt.run_container(
            image="alpine:latest",
            command=["echo", "hello"],
            env={"FOO": "bar"},
            timeout=60,
        )
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "podman"
        assert cmd[1] == "run"
        assert container_id == "podman-container-id"

    @patch("src.serverless.container_runtime.uuid.uuid4")
    @patch("src.serverless.container_runtime.subprocess.run")
    def test_run_container_includes_security_flags(self, mock_run, mock_uuid):
        """Podman applies the same security flags as Docker."""
        mock_uuid.return_value = "test-uuid-podman-sec"
        mock_run.return_value = MagicMock(
            returncode=0, stdout="podman-cid\n", stderr=""
        )
        rt = PodmanRuntime()
        rt.run_container(
            image="python:3.11",
            command=["python", "app.py"],
            env={"ENV_VAR": "test"},
            timeout=120,
        )
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "podman"
        assert "--read-only" in cmd
        assert "--user" in cmd
        assert "nobody" in cmd
        assert "--cap-drop" in cmd
        assert "ALL" in cmd
        assert "--memory" in cmd
        assert "--cpus" in cmd
        assert "--network" in cmd
        assert "none" in cmd
        assert "--security-opt" in cmd
        assert "no-new-privileges" in cmd
        assert "--pids-limit" in cmd
        assert "256" in cmd
        # Verify env passed
        assert "-e" in cmd
        assert "ENV_VAR=test" in cmd
        # Image and command at end
        assert cmd[-3] == "python:3.11"
        assert cmd[-2] == "python"
        assert cmd[-1] == "app.py"

    @patch("src.serverless.container_runtime.subprocess.run")
    def test_stop_container_uses_podman(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        rt = PodmanRuntime()
        rt.stop_container("abc123", timeout=5)
        mock_run.assert_called_once_with(
            ["podman", "stop", "-t", "5", "abc123"],
            capture_output=True,
            text=True,
        )

    @patch("src.serverless.container_runtime.subprocess.run")
    def test_get_logs_uses_podman(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="output\n", stderr=""
        )
        rt = PodmanRuntime()
        rt.get_logs("abc123", stream="stdout")
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "podman"
        assert "logs" in cmd

    @patch("src.serverless.container_runtime.subprocess.run")
    def test_wait_uses_podman(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="0\n", stderr="")
        rt = PodmanRuntime()
        exit_code = rt.wait("abc123", timeout=300)
        assert exit_code == 0
        mock_run.assert_called_once_with(
            ["podman", "wait", "abc123"],
            capture_output=True,
            text=True,
            timeout=300,
        )

    @patch("src.serverless.container_runtime.subprocess.run")
    def test_cleanup_uses_podman(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        rt = PodmanRuntime()
        rt.cleanup("abc123")
        mock_run.assert_called_once_with(
            ["podman", "rm", "-f", "abc123"],
            capture_output=True,
            text=True,
        )


class TestContainerRuntimeDetect:
    """Test the detect() static method for runtime auto-detection."""

    @patch("src.serverless.container_runtime.subprocess.run")
    @patch("src.serverless.container_runtime.shutil.which")
    def test_detect_returns_docker_when_available(self, mock_which, mock_run):
        mock_which.return_value = "/usr/bin/docker"
        mock_run.return_value = MagicMock(
            returncode=0, stdout="Docker version 24.0.7\n", stderr=""
        )
        runtime = ContainerRuntime.detect()
        assert isinstance(runtime, DockerRuntime)
        mock_which.assert_called_with("docker")

    @patch("src.serverless.container_runtime.subprocess.run")
    @patch("src.serverless.container_runtime.shutil.which")
    def test_detect_returns_podman_when_docker_not_available(self, mock_which, mock_run):
        def which_side_effect(binary):
            if binary == "docker":
                return None
            if binary == "podman":
                return "/usr/bin/podman"
            return None

        mock_which.side_effect = which_side_effect
        mock_run.return_value = MagicMock(
            returncode=0, stdout="podman version 4.7.0\n", stderr=""
        )
        runtime = ContainerRuntime.detect()
        assert isinstance(runtime, PodmanRuntime)

    @patch("src.serverless.container_runtime.subprocess.run")
    @patch("src.serverless.container_runtime.shutil.which")
    def test_detect_raises_when_no_runtime_available(self, mock_which, mock_run):
        mock_which.return_value = None
        with pytest.raises(RuntimeError, match="No supported container runtime found"):
            ContainerRuntime.detect()

    @patch("src.serverless.container_runtime.subprocess.run")
    @patch("src.serverless.container_runtime.shutil.which")
    def test_detect_falls_back_to_podman_when_docker_fails(self, mock_which, mock_run):
        def which_side_effect(binary):
            return f"/usr/bin/{binary}"

        mock_which.side_effect = which_side_effect

        def run_side_effect(cmd, **kwargs):
            if cmd[0] == "docker":
                return MagicMock(returncode=1, stdout="", stderr="error")
            return MagicMock(returncode=0, stdout="podman version 4.7.0\n", stderr="")

        mock_run.side_effect = run_side_effect
        runtime = ContainerRuntime.detect()
        assert isinstance(runtime, PodmanRuntime)

    @patch("src.serverless.container_runtime.subprocess.run")
    @patch("src.serverless.container_runtime.shutil.which")
    def test_detect_prefers_docker_over_podman(self, mock_which, mock_run):
        # Both are available, Docker should be preferred
        mock_which.return_value = "/usr/bin/docker"
        mock_run.return_value = MagicMock(
            returncode=0, stdout="Docker version 24.0.7\n", stderr=""
        )
        runtime = ContainerRuntime.detect()
        assert isinstance(runtime, DockerRuntime)

    @patch("src.serverless.container_runtime.subprocess.run")
    @patch("src.serverless.container_runtime.shutil.which")
    def test_detect_handles_oserror_for_docker(self, mock_which, mock_run):
        def which_side_effect(binary):
            return f"/usr/bin/{binary}"

        mock_which.side_effect = which_side_effect

        def run_side_effect(cmd, **kwargs):
            if cmd[0] == "docker":
                raise OSError("Permission denied")
            return MagicMock(returncode=0, stdout="podman version 4.7.0\n", stderr="")

        mock_run.side_effect = run_side_effect
        runtime = ContainerRuntime.detect()
        assert isinstance(runtime, PodmanRuntime)
