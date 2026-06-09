"""Tests for DELETE /api/servers/<server_id>/gpu/instances endpoint.

Verifies authentication, server existence, instance existence check,
SSH command execution, partial failure handling, and successful destruction.
"""

import json
from unittest.mock import patch, MagicMock, call

import pytest
from flask import Flask

from src.routes.gpu_routes import gpu_bp


@pytest.fixture
def app():
    """Create a Flask app with the GPU blueprint for testing."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.register_blueprint(gpu_bp)
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


class TestDeleteInstancesAuth:
    """Test authentication and authorization for DELETE /instances."""

    def test_returns_401_when_not_authenticated(self, client):
        response = client.delete('/api/servers/1/gpu/instances')
        assert response.status_code == 401
        data = response.get_json()
        assert data['error'] == 'Authentication required'

    def test_returns_403_when_not_admin(self, client):
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['is_admin'] = False
        response = client.delete('/api/servers/1/gpu/instances')
        assert response.status_code == 403
        data = response.get_json()
        assert data['error'] == 'Admin access required'


class TestDeleteInstancesServerNotFound:
    """Test server existence check for DELETE /instances."""

    @patch('src.routes.gpu_routes.db_manager')
    def test_returns_404_when_server_not_found(self, mock_db, client):
        mock_db.execute_query.return_value = None
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['is_admin'] = True
        response = client.delete('/api/servers/999/gpu/instances')
        assert response.status_code == 404
        data = response.get_json()
        assert data['error'] == 'Server not found'


class TestDeleteInstancesNoInstances:
    """Test behavior when no MIG instances exist."""

    @patch('src.routes.gpu_routes.db_manager')
    def test_returns_400_when_no_instances_exist(self, mock_db, client):
        # First call: get_server_ip returns IP
        # Second call: SELECT COUNT(*) returns 0
        mock_db.execute_query.side_effect = [('192.168.1.10',), (0,)]
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['is_admin'] = True
        response = client.delete('/api/servers/1/gpu/instances')
        assert response.status_code == 400
        data = response.get_json()
        assert data['error'] == 'No MIG instances configured on this server'


class TestDeleteInstancesSSHFailures:
    """Test SSH command failure handling."""

    @patch('src.routes.gpu_routes.ssh_execute')
    @patch('src.routes.gpu_routes.db_manager')
    def test_returns_500_when_dci_fails(self, mock_db, mock_ssh, client):
        # get_server_ip returns IP, COUNT returns 3
        mock_db.execute_query.side_effect = [('192.168.1.10',), (3,)]
        # -dci fails
        mock_ssh.return_value = (False, '', 'Error: no MIG compute instances to destroy')
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['is_admin'] = True
        response = client.delete('/api/servers/1/gpu/instances')
        assert response.status_code == 500
        data = response.get_json()
        assert 'Failed to destroy compute instances' in data['error']
        # Should not attempt -dgi or delete DB records
        mock_ssh.assert_called_once_with('192.168.1.10', 'sudo nvidia-smi mig -dci', timeout=30)

    @patch('src.routes.gpu_routes.ssh_execute')
    @patch('src.routes.gpu_routes.db_manager')
    def test_returns_500_when_dgi_fails_after_dci_succeeds(self, mock_db, mock_ssh, client):
        # get_server_ip returns IP, COUNT returns 2
        mock_db.execute_query.side_effect = [('192.168.1.10',), (2,)]
        # -dci succeeds, -dgi fails
        mock_ssh.side_effect = [
            (True, 'Successfully destroyed compute instances', ''),
            (False, '', 'Error: could not destroy GPU instances'),
        ]
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['is_admin'] = True
        response = client.delete('/api/servers/1/gpu/instances')
        assert response.status_code == 500
        data = response.get_json()
        assert 'inconsistent state' in data['error']
        # DB records should NOT be deleted (only 2 calls: get_server_ip and COUNT)
        assert mock_db.execute_query.call_count == 2

    @patch('src.routes.gpu_routes.ssh_execute')
    @patch('src.routes.gpu_routes.db_manager')
    def test_truncates_stderr_to_4096_chars(self, mock_db, mock_ssh, client):
        mock_db.execute_query.side_effect = [('192.168.1.10',), (1,)]
        long_error = 'x' * 5000
        mock_ssh.return_value = (False, '', long_error)
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['is_admin'] = True
        response = client.delete('/api/servers/1/gpu/instances')
        assert response.status_code == 500
        data = response.get_json()
        # Error message should be truncated to 4096 chars max
        assert len(data['error']) <= 4096 + len('Failed to destroy compute instances: ')


class TestDeleteInstancesSuccess:
    """Test successful instance destruction."""

    @patch('src.routes.gpu_routes.ssh_execute')
    @patch('src.routes.gpu_routes.db_manager')
    def test_returns_200_with_count_on_success(self, mock_db, mock_ssh, client):
        # get_server_ip returns IP, COUNT returns 3, DELETE returns None
        mock_db.execute_query.side_effect = [('192.168.1.10',), (3,), None]
        # Both SSH commands succeed
        mock_ssh.side_effect = [
            (True, 'Successfully destroyed compute instances', ''),
            (True, 'Successfully destroyed GPU instances', ''),
        ]
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['is_admin'] = True
        response = client.delete('/api/servers/1/gpu/instances')
        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'All MIG instances destroyed'
        assert data['count'] == 3

    @patch('src.routes.gpu_routes.ssh_execute')
    @patch('src.routes.gpu_routes.db_manager')
    def test_deletes_db_records_on_success(self, mock_db, mock_ssh, client):
        mock_db.execute_query.side_effect = [('10.0.0.5',), (5,), None]
        mock_ssh.side_effect = [
            (True, '', ''),
            (True, '', ''),
        ]
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['is_admin'] = True
        client.delete('/api/servers/7/gpu/instances')
        # Third call should be the DELETE FROM query
        delete_call = mock_db.execute_query.call_args_list[2]
        assert 'DELETE FROM mig_instances WHERE server_id' in delete_call[0][0]
        assert delete_call[0][1] == (7,)

    @patch('src.routes.gpu_routes.ssh_execute')
    @patch('src.routes.gpu_routes.db_manager')
    def test_ssh_commands_called_in_order(self, mock_db, mock_ssh, client):
        mock_db.execute_query.side_effect = [('192.168.1.10',), (2,), None]
        mock_ssh.side_effect = [
            (True, '', ''),
            (True, '', ''),
        ]
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['is_admin'] = True
        client.delete('/api/servers/1/gpu/instances')
        # Verify the order of SSH calls
        assert mock_ssh.call_args_list == [
            call('192.168.1.10', 'sudo nvidia-smi mig -dci', timeout=30),
            call('192.168.1.10', 'sudo nvidia-smi mig -dgi', timeout=30),
        ]
