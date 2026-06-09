"""Unit tests for parse_mig_profiles function."""
import pytest
from src.routes.gpu_routes import parse_mig_profiles


class TestParseMigProfiles:
    """Tests for parsing nvidia-smi mig -lgip output."""

    def test_typical_output_three_profiles(self):
        """Parse a typical nvidia-smi output with three MIG profiles."""
        output = """\
+-----------------------------------------------------------------------------+
| GPU instance profiles:                                                       |
| GPU   Name             ID    Instances   Memory     P2P    SM    DEC   ENC  |
|                              Free/Total   GiB              CE    JPEG  OFA  |
|=============================================================================|
|   0  MIG 1g.10gb       9     7/7        9.50       No     16     1     0   |
|                                                            1      0     0   |
+-----------------------------------------------------------------------------+
|   0  MIG 2g.20gb      14     3/3        19.50      No     32     2     0   |
|                                                            2      0     0   |
+-----------------------------------------------------------------------------+
|   0  MIG 4g.40gb      19     1/1        39.50      No     64     4     0   |
|                                                            4      0     0   |
+-----------------------------------------------------------------------------+
"""
        result = parse_mig_profiles(output)

        assert len(result) == 3

        assert result[0]['profile_id'] == 9
        assert result[0]['name'] == 'MIG 1g.10gb'
        assert result[0]['memory_mib'] == int(9.50 * 1024)

        assert result[1]['profile_id'] == 14
        assert result[1]['name'] == 'MIG 2g.20gb'
        assert result[1]['memory_mib'] == int(19.50 * 1024)

        assert result[2]['profile_id'] == 19
        assert result[2]['name'] == 'MIG 4g.40gb'
        assert result[2]['memory_mib'] == int(39.50 * 1024)

    def test_empty_output(self):
        """Empty string returns empty list."""
        assert parse_mig_profiles('') == []

    def test_none_output(self):
        """None input returns empty list."""
        assert parse_mig_profiles(None) == []

    def test_whitespace_only_output(self):
        """Whitespace-only input returns empty list."""
        assert parse_mig_profiles('   \n  \t  \n') == []

    def test_malformed_lines_ignored(self):
        """Lines that don't match the expected pattern are skipped."""
        output = """\
+-----------------------------------------------------------------------------+
| GPU instance profiles:                                                       |
| Some random garbage line                                                     |
|   0  MIG 1g.10gb       9     7/7        9.50       No     16     1     0   |
| Another malformed line without proper fields                                 |
+-----------------------------------------------------------------------------+
"""
        result = parse_mig_profiles(output)
        assert len(result) == 1
        assert result[0]['profile_id'] == 9
        assert result[0]['name'] == 'MIG 1g.10gb'

    def test_extra_whitespace_in_lines(self):
        """Lines with extra whitespace are still parsed correctly."""
        output = """\
|   0   MIG 1g.10gb       9      7/7         9.50        No      16      1      0   |
"""
        result = parse_mig_profiles(output)
        assert len(result) == 1
        assert result[0]['profile_id'] == 9
        assert result[0]['name'] == 'MIG 1g.10gb'
        assert result[0]['memory_mib'] == int(9.50 * 1024)

    def test_single_profile(self):
        """Parse output with only one profile entry."""
        output = """\
+-----------------------------------------------------------------------------+
| GPU instance profiles:                                                       |
|=============================================================================|
|   0  MIG 7g.80gb       0     1/1        79.25      No     132    7     0   |
|                                                            7      1     0   |
+-----------------------------------------------------------------------------+
"""
        result = parse_mig_profiles(output)
        assert len(result) == 1
        assert result[0]['profile_id'] == 0
        assert result[0]['name'] == 'MIG 7g.80gb'
        assert result[0]['memory_mib'] == int(79.25 * 1024)

    def test_memory_conversion_gib_to_mib(self):
        """Memory values are correctly converted from GiB to MiB (x1024)."""
        output = """\
|   0  MIG 1g.5gb        5     7/7        4.75       No     14     1     0   |
"""
        result = parse_mig_profiles(output)
        assert len(result) == 1
        # 4.75 GiB = 4864 MiB
        assert result[0]['memory_mib'] == 4864

    def test_no_matching_lines(self):
        """Output with only headers/separators and no data returns empty list."""
        output = """\
+-----------------------------------------------------------------------------+
| GPU instance profiles:                                                       |
| GPU   Name             ID    Instances   Memory     P2P    SM    DEC   ENC  |
|                              Free/Total   GiB              CE    JPEG  OFA  |
|=============================================================================|
+-----------------------------------------------------------------------------+
"""
        result = parse_mig_profiles(output)
        assert len(result) == 0

    def test_result_dict_keys(self):
        """Each result dict has exactly the expected keys."""
        output = """\
|   0  MIG 1g.10gb       9     7/7        9.50       No     16     1     0   |
"""
        result = parse_mig_profiles(output)
        assert len(result) == 1
        assert set(result[0].keys()) == {'profile_id', 'name', 'memory_mib'}

    def test_profile_id_is_int(self):
        """profile_id is always an integer."""
        output = """\
|   0  MIG 2g.20gb      14     3/3        19.50      No     32     2     0   |
"""
        result = parse_mig_profiles(output)
        assert isinstance(result[0]['profile_id'], int)

    def test_memory_mib_is_int(self):
        """memory_mib is always an integer."""
        output = """\
|   0  MIG 2g.20gb      14     3/3        19.50      No     32     2     0   |
"""
        result = parse_mig_profiles(output)
        assert isinstance(result[0]['memory_mib'], int)
