"""
SEED Platform (TM), Copyright (c) Alliance for Sustainable Energy, LLC, and other contributors.
See also https://github.com/SEED-platform/building-data-utilities/blob/main/LICENSE.md
"""

from building_data_utilities.standardize_address_fields import standardize_address_fields


class TestStandardizeAddressFields:
    """Tests for standardizing address field names/values across records."""

    def test_standardize_address_fields_success(self):
        data = [
            {"street_addr": "123 Main St", "municipality": "Denver", "province": "Colorado", "zip": "80202"},
            {"address": "456 Oak Ave", "city": "Boulder", "state": "CO", "postal_code": "80301"},
        ]

        result = standardize_address_fields(data)

        assert len(result) == 2

        # Check first record
        assert result[0]["street_address"] == "123 Main St"
        assert result[0]["city"] == "Denver"
        assert result[0]["state"] == "CO"
        assert result[0]["postal_code"] == "80202"

        # Check second record
        assert result[1]["street_address"] == "456 Oak Ave"
        assert result[1]["city"] == "Boulder"
        assert result[1]["state"] == "CO"
        assert result[1]["postal_code"] == "80301"

    def test_standardize_address_fields_with_normalization(self):
        data = [
            {
                "address": "123 Main St",
                "city": "Denver",
                "state": "Colorado",  # Should be normalized to CO
            }
        ]

        result = standardize_address_fields(data)

        assert result[0]["state"] == "CO"

    def test_standardize_address_fields_preserve_other_fields(self):
        data = [{"street_address": "123 Main St", "city": "Denver", "state": "CO", "building_type": "Commercial", "height": 50}]

        result = standardize_address_fields(data)

        assert result[0]["building_type"] == "Commercial"
        assert result[0]["height"] == 50
