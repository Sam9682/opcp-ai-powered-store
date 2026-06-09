"""Unit tests for validate_profile_ids() function."""
import sys
import os

# Add project root to path so we can import the module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.routes.gpu_routes import validate_profile_ids


class TestValidateProfileIds:
    """Tests for validate_profile_ids validation function."""

    def test_empty_list_rejected(self):
        """Empty profile_ids list should return error message."""
        result = validate_profile_ids([])
        assert result == "profile_ids must contain 1 to 7 entries"

    def test_more_than_7_entries_rejected(self):
        """Lists with more than 7 entries should return error message."""
        ids = ["1", "2", "3", "4", "5", "6", "7", "8"]
        result = validate_profile_ids(ids)
        assert result == "profile_ids must contain 1 to 7 entries"

    def test_single_entry_valid(self):
        """A single profile ID should be valid."""
        result = validate_profile_ids(["9"])
        assert result is None

    def test_seven_entries_valid(self):
        """Exactly 7 entries should be valid (upper boundary)."""
        ids = ["1", "2", "3", "4", "5", "6", "7"]
        result = validate_profile_ids(ids)
        assert result is None

    def test_mid_range_valid(self):
        """3 entries should be valid (mid-range)."""
        ids = ["9", "14", "9"]
        result = validate_profile_ids(ids)
        assert result is None
