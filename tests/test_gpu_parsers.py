"""Tests for GPU routes parser functions.

Verifies parse_mig_instances correctly extracts MIG instance UUIDs and
profile names from nvidia-smi -L output.
"""

import sys
from unittest.mock import MagicMock

import pytest

# Mock psycopg2 and related modules before importing gpu_routes
mock_psycopg2 = MagicMock()
mock_psycopg2.pool = MagicMock()
mock_psycopg2.extras = MagicMock()
sys.modules.setdefault("psycopg2", mock_psycopg2)
sys.modules.setdefault("psycopg2.pool", mock_psycopg2.pool)
sys.modules.setdefault("psycopg2.extras", mock_psycopg2.extras)

from src.routes.gpu_routes import parse_mig_instances


class TestParseMigInstances:
    """Test parse_mig_instances with various nvidia-smi -L outputs."""

    def test_single_gpu_with_mig_instances(self):
        """Parse output with one GPU and multiple MIG instances."""
        output = (
            "GPU 0: NVIDIA H100 80GB HBM3 (UUID: GPU-12345678-abcd-efgh-ijkl-123456789abc)\n"
            "  MIG 1g.10gb     Device  0: (UUID: MIG-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee)\n"
            "  MIG 1g.10gb     Device  1: (UUID: MIG-ffffffff-1111-2222-3333-444444444444)\n"
            "  MIG 2g.20gb     Device  2: (UUID: MIG-55555555-6666-7777-8888-999999999999)\n"
        )
        result = parse_mig_instances(output)
        assert len(result) == 3
        assert result[0] == {
            'instance_uuid': 'MIG-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
            'profile_name': '1g.10gb'
        }
        assert result[1] == {
            'instance_uuid': 'MIG-ffffffff-1111-2222-3333-444444444444',
            'profile_name': '1g.10gb'
        }
        assert result[2] == {
            'instance_uuid': 'MIG-55555555-6666-7777-8888-999999999999',
            'profile_name': '2g.20gb'
        }

    def test_no_mig_devices(self):
        """Parse output with GPU but no MIG instances."""
        output = (
            "GPU 0: NVIDIA H100 80GB HBM3 (UUID: GPU-12345678-abcd-efgh-ijkl-123456789abc)\n"
        )
        result = parse_mig_instances(output)
        assert result == []

    def test_empty_output(self):
        """Parse empty string output."""
        result = parse_mig_instances("")
        assert result == []

    def test_none_output(self):
        """Parse None output."""
        result = parse_mig_instances(None)
        assert result == []

    def test_multiple_gpus_with_mig_instances(self):
        """Parse output with multiple GPUs each having MIG instances."""
        output = (
            "GPU 0: NVIDIA H100 80GB HBM3 (UUID: GPU-11111111-aaaa-bbbb-cccc-111111111111)\n"
            "  MIG 1g.10gb     Device  0: (UUID: MIG-aaaaaaaa-1111-2222-3333-aaaaaaaaaaaa)\n"
            "  MIG 2g.20gb     Device  1: (UUID: MIG-bbbbbbbb-4444-5555-6666-bbbbbbbbbbbb)\n"
            "GPU 1: NVIDIA H100 80GB HBM3 (UUID: GPU-22222222-dddd-eeee-ffff-222222222222)\n"
            "  MIG 4g.40gb     Device  0: (UUID: MIG-cccccccc-7777-8888-9999-cccccccccccc)\n"
        )
        result = parse_mig_instances(output)
        assert len(result) == 3
        assert result[0]['instance_uuid'] == 'MIG-aaaaaaaa-1111-2222-3333-aaaaaaaaaaaa'
        assert result[0]['profile_name'] == '1g.10gb'
        assert result[1]['instance_uuid'] == 'MIG-bbbbbbbb-4444-5555-6666-bbbbbbbbbbbb'
        assert result[1]['profile_name'] == '2g.20gb'
        assert result[2]['instance_uuid'] == 'MIG-cccccccc-7777-8888-9999-cccccccccccc'
        assert result[2]['profile_name'] == '4g.40gb'

    def test_mixed_output_with_non_mig_lines(self):
        """Parse output containing non-MIG lines mixed in."""
        output = (
            "GPU 0: NVIDIA H100 80GB HBM3 (UUID: GPU-12345678-abcd-efgh-ijkl-123456789abc)\n"
            "Some random log line\n"
            "  MIG 1g.10gb     Device  0: (UUID: MIG-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee)\n"
            "Another random line\n"
            "  MIG 3g.40gb     Device  1: (UUID: MIG-12345678-abcd-1234-abcd-123456789abc)\n"
        )
        result = parse_mig_instances(output)
        assert len(result) == 2
        assert result[0]['profile_name'] == '1g.10gb'
        assert result[1]['profile_name'] == '3g.40gb'

    def test_various_profile_names(self):
        """Parse output with different MIG profile name formats."""
        output = (
            "GPU 0: NVIDIA H100 (UUID: GPU-12345678-abcd-efgh-ijkl-123456789abc)\n"
            "  MIG 1g.5gb      Device  0: (UUID: MIG-11111111-2222-3333-4444-555555555555)\n"
            "  MIG 2g.10gb     Device  1: (UUID: MIG-22222222-3333-4444-5555-666666666666)\n"
            "  MIG 3g.20gb     Device  2: (UUID: MIG-33333333-4444-5555-6666-777777777777)\n"
            "  MIG 4g.40gb     Device  3: (UUID: MIG-44444444-5555-6666-7777-888888888888)\n"
            "  MIG 7g.80gb     Device  4: (UUID: MIG-55555555-6666-7777-8888-999999999999)\n"
        )
        result = parse_mig_instances(output)
        assert len(result) == 5
        assert result[0]['profile_name'] == '1g.5gb'
        assert result[1]['profile_name'] == '2g.10gb'
        assert result[2]['profile_name'] == '3g.20gb'
        assert result[3]['profile_name'] == '4g.40gb'
        assert result[4]['profile_name'] == '7g.80gb'

    def test_uppercase_hex_in_uuid(self):
        """Parse output with uppercase hex characters in MIG UUID."""
        output = (
            "GPU 0: NVIDIA H100 (UUID: GPU-12345678-ABCD-EFGH-IJKL-123456789ABC)\n"
            "  MIG 1g.10gb     Device  0: (UUID: MIG-AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE)\n"
        )
        result = parse_mig_instances(output)
        assert len(result) == 1
        assert result[0]['instance_uuid'] == 'MIG-AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE'
        assert result[0]['profile_name'] == '1g.10gb'
