"""Tests for PUT /api/servers/<server_id>/gpu/enabled endpoint.

Verifies authentication, request validation, server existence checks,
and successful toggling of the shared_gpu_enabled flag.
"""

import json
from unittest.mock import patch, MagicMock

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


class TestPutEnabledAuth:
    """Test authentication and authorization for PUT /enabled."""

    def test_returns_401_when_not_authenticated(self, client):
        response = client.put(
            '/api/servers/1/gpu/enabled',
            data=json.dumps({'enabled': True}),
            content_type='application/json',
        )
        assert response.status_code == 401
        data = response.get_json()
        assert data['error'] == 'Authentication required'

    def test_returns_403_when_not_admin(self, client):
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['is_admin'] = False
        response = client.put(
            '/api/servers/1/gpu/enabled',
            data=json.dumps({'enabled': True}),
            content_type='application/json',
        )
        assert response.status_code == 403
        data = response.get_json()
        assert data['error'] == 'Admin access required'


class TestPutEnabledValidation:
    """Test request body validation for PUT /enabled."""

    def test_returns_400_when_body_is_missing(self, client):
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['is_admin'] = True
        response = client.put(
            '/api/servers/1/gpu/enabled',
            content_type='application/json',
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data['error'] == "Field 'enabled' must be a boolean"

    def test_returns_400_when_enabled_field_is_missing(self, client):
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['is_admin'] = True
        response = client.put(
            '/api/servers/1/gpu/enabled',
            data=json.dumps({'other': 'value'}),
            content_type='application/json',
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data['error'] == "Field 'enabled' must be a boolean"

    def test_returns_400_when_enabled_is_not_boolean(self, client):
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['is_admin'] = True
        response = client.put(
            '/api/servers/1/gpu/enabled',
            data=json.dumps({'enabled': 'yes'}),
            content_type='application/json',
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data['error'] == "Field 'enabled' must be a boolean"

    def test_returns_400_when_enabled_is_integer(self, client):
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['is_admin'] = True
        response = client.put(
            '/api/servers/1/gpu/enabled',
            data=json.dumps({'enabled': 1}),
            content_type='application/json',
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data['error'] == "Field 'enabled' must be a boolean"


class TestPutEnabledServerNotFound:
    """Test server existence check for PUT /enabled."""

    @patch('src.routes.gpu_routes.db_manager')
    def test_returns_404_when_server_not_found(self, mock_db, client):
        mock_db.execute_query.return_value = None
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['is_admin'] = True
        response = client.put(
            '/api/servers/999/gpu/enabled',
            data=json.dumps({'enabled': True}),
            content_type='application/json',
        )
        assert response.status_code == 404
        data = response.get_json()
        assert data['error'] == 'Server not found'


class TestPutEnabledSuccess:
    """Test successful toggling of shared_gpu_enabled."""

    @patch('src.routes.gpu_routes.ssh_execute')
    @patch('src.routes.gpu_routes.db_manager')
    def test_enables_shared_gpu(self, mock_db, mock_ssh, client):
        # First call: get_server_ip returns an IP
        # Second call: UPDATE query (set enabled=true)
        mock_db.execute_query.side_effect = [('192.168.1.10',), None]
        # SSH call to enable MIG mode succeeds
        mock_ssh.return_value = (True, 'MIG mode enabled', '')
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['is_admin'] = True
        response = client.put(
            '/api/servers/1/gpu/enabled',
            data=json.dumps({'enabled': True}),
            content_type='application/json',
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data == {'server_id': 1, 'shared_gpu_enabled': True}
        # Verify SSH was called with MIG enable command
        mock_ssh.assert_called_once_with('192.168.1.10', 'sudo nvidia-smi -mig 1', timeout=30)

    @patch('src.routes.gpu_routes.ssh_execute')
    @patch('src.routes.gpu_routes.db_manager')
    def test_disables_shared_gpu(self, mock_db, mock_ssh, client):
        mock_db.execute_query.side_effect = [('192.168.1.10',), None]
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['is_admin'] = True
        response = client.put(
            '/api/servers/1/gpu/enabled',
            data=json.dumps({'enabled': False}),
            content_type='application/json',
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data == {'server_id': 1, 'shared_gpu_enabled': False}
        # Verify SSH was NOT called when disabling
        mock_ssh.assert_not_called()

    @patch('src.routes.gpu_routes.ssh_execute')
    @patch('src.routes.gpu_routes.db_manager')
    def test_calls_update_query_with_correct_params(self, mock_db, mock_ssh, client):
        mock_db.execute_query.side_effect = [('10.0.0.1',), None]
        mock_ssh.return_value = (True, '', '')
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['is_admin'] = True
        client.put(
            '/api/servers/5/gpu/enabled',
            data=json.dumps({'enabled': True}),
            content_type='application/json',
        )
        # Second call should be the UPDATE
        update_call = mock_db.execute_query.call_args_list[1]
        assert 'UPDATE servers SET shared_gpu_enabled' in update_call[0][0]
        assert update_call[0][1] == (True, 5)


class TestPutEnabledMigFailure:
    """Test MIG mode command failure and DB revert behavior."""

    @patch('src.routes.gpu_routes.ssh_execute')
    @patch('src.routes.gpu_routes.db_manager')
    def test_reverts_db_on_mig_command_failure(self, mock_db, mock_ssh, client):
        # get_server_ip returns IP, first UPDATE succeeds, revert UPDATE succeeds
        mock_db.execute_query.side_effect = [('192.168.1.10',), None, None]
        # SSH MIG command fails
        mock_ssh.return_value = (False, '', 'GPU not found or not supported')
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['is_admin'] = True
        response = client.put(
            '/api/servers/1/gpu/enabled',
            data=json.dumps({'enabled': True}),
            content_type='application/json',
        )
        assert response.status_code == 500
        data = response.get_json()
        assert 'MIG mode could not be enabled' in data['error']
        assert 'GPU not found or not supported' in data['error']
        # Verify revert query was called (third DB call)
        revert_call = mock_db.execute_query.call_args_list[2]
        assert 'UPDATE servers SET shared_gpu_enabled' in revert_call[0][0]
        assert revert_call[0][1] == (False, 1)

    @patch('src.routes.gpu_routes.ssh_execute')
    @patch('src.routes.gpu_routes.db_manager')
    def test_reverts_db_on_mig_timeout(self, mock_db, mock_ssh, client):
        mock_db.execute_query.side_effect = [('10.0.0.5',), None, None]
        mock_ssh.return_value = (False, '', 'Command timed out after 30 seconds')
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['is_admin'] = True
        response = client.put(
            '/api/servers/2/gpu/enabled',
            data=json.dumps({'enabled': True}),
            content_type='application/json',
        )
        assert response.status_code == 500
        data = response.get_json()
        assert 'MIG mode could not be enabled' in data['error']

    @patch('src.routes.gpu_routes.ssh_execute')
    @patch('src.routes.gpu_routes.db_manager')
    def test_no_ssh_call_when_disabling(self, mock_db, mock_ssh, client):
        """Disabling should only update DB, no SSH call."""
        mock_db.execute_query.side_effect = [('192.168.1.10',), None]
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['is_admin'] = True
        response = client.put(
            '/api/servers/1/gpu/enabled',
            data=json.dumps({'enabled': False}),
            content_type='application/json',
        )
        assert response.status_code == 200
        mock_ssh.assert_not_called()
        # Only 2 DB calls: get_server_ip + UPDATE (no revert)
        assert mock_db.execute_query.call_count == 2
