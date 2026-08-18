"""
SEED Platform (TM), Copyright (c) Alliance for Sustainable Energy, LLC, and other contributors.
See also https://github.com/SEED-platform/building-data-utilities/blob/main/LICENSE.md
"""

from building_data_utilities.normalize_state import normalize_state


class TestNormalizeState:
    """Tests for state name/abbreviation normalization."""

    def test_normalize_state_full_name(self):
        test_cases = [
            ("colorado", "CO"),
            ("Colorado", "CO"),
            ("COLORADO", "CO"),
            ("california", "CA"),
            ("new york", "NY"),
            ("district of columbia", "DC"),
        ]

        for input_state, expected in test_cases:
            result = normalize_state(input_state)
            assert result == expected, f"Failed for input: {input_state}"

    def test_normalize_state_abbreviation(self):
        test_cases = [("co", "CO"), ("CO", "CO"), ("ca", "CA"), ("NY", "NY")]

        for input_state, expected in test_cases:
            result = normalize_state(input_state)
            assert result == expected, f"Failed for input: {input_state}"

    def test_normalize_state_unknown(self):
        assert normalize_state("Unknown State") == "UNKNOWN STATE"

    def test_normalize_state_empty(self):
        assert normalize_state("") == ""
        assert normalize_state(None) == ""
