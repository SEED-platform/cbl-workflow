"""
SEED Platform (TM), Copyright (c) Alliance for Sustainable Energy, LLC, and other contributors.
See also https://github.com/SEED-platform/building-data-utilities/blob/main/LICENSE.md
"""

from building_data_utilities.generate_locations_list import _extract_field, generate_locations_list


class TestGenerateLocationsList:
    """Tests for building a list of Location objects from user-supplied records."""

    def test_generate_locations_list_success(self):
        records = [
            {"street_address": "123 Main St", "city": "Denver", "state": "Colorado"},
            {"Street_Address": "456 Oak Ave", "City": "Boulder", "State": "CO"},
        ]

        result = generate_locations_list(records)

        assert len(result) == 2
        assert result[0]["street"] == "123 Main St"
        assert result[0]["city"] == "Denver"
        assert result[0]["state"] == "CO"  # Should be normalized

        assert result[1]["street"] == "456 Oak Ave"
        assert result[1]["city"] == "Boulder"
        assert result[1]["state"] == "CO"

    def test_generate_locations_list_missing_fields(self):
        incomplete_records = [
            {"city": "Denver"},  # Missing street and state
            {"street_address": "456 Oak Ave"},  # Missing city and state
        ]

        result = generate_locations_list(incomplete_records)

        assert len(result) == 2
        assert result[0]["street"] == ""
        assert result[0]["city"] == "Denver"
        assert result[0]["state"] == ""

        assert result[1]["street"] == "456 Oak Ave"
        assert result[1]["city"] == ""
        assert result[1]["state"] == ""

    def test_extract_field_case_insensitive(self):
        record = {"Street_Address": "123 Main St", "CITY": "Denver", "state": "CO"}

        assert _extract_field(record, "street_address") == "123 Main St"
        assert _extract_field(record, "city") == "Denver"
        assert _extract_field(record, "STATE") == "CO"

    def test_extract_field_not_found(self):
        record = {"other_field": "value"}

        assert _extract_field(record, "street_address") is None
