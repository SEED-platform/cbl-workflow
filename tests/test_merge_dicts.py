"""
SEED Platform (TM), Copyright (c) Alliance for Sustainable Energy, LLC, and other contributors.
See also https://github.com/SEED-platform/building-data-utilities/blob/main/LICENSE.md
"""

from building_data_utilities.merge_dicts import merge_dicts


class TestMergeDicts:
    """Tests for the generic dict-merge helper."""

    def test_merge_dicts_success(self):
        dict1 = {"name": "Test", "city": "Denver", "original_field": "value1"}
        dict2 = {"city": "Boulder", "state": "CO", "processed_field": "value2"}

        result = merge_dicts(dict1, dict2)

        # dict2 values should override dict1
        assert result["city"] == "Boulder"
        # dict1 values should remain if not in dict2
        assert result["name"] == "Test"
        assert result["original_field"] == "value1"
        # dict2 values should be included
        assert result["state"] == "CO"
        assert result["processed_field"] == "value2"

    def test_merge_dicts_empty_dicts(self):
        assert merge_dicts({}, {}) == {}

    def test_merge_dicts_one_empty(self):
        assert merge_dicts({"key1": "value1"}, {}) == {"key1": "value1"}
        assert merge_dicts({}, {"key2": "value2"}) == {"key2": "value2"}
