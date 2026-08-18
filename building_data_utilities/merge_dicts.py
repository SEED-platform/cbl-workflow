"""
SEED Platform (TM), Copyright (c) Alliance for Sustainable Energy, LLC, and other contributors.
See also https://github.com/SEED-platform/building-data-utilities/blob/main/LICENSE.md
"""


def merge_dicts(dict1: dict, dict2: dict) -> dict:
    """
    Merge two dictionaries, with dict2 values taking precedence over dict1.

    Args:
        dict1: First dictionary (typically original/base data)
        dict2: Second dictionary (typically newer/overriding data)

    Returns:
        Merged dictionary with dict2 values overriding dict1 values
    """
    merged = dict1.copy()
    merged.update(dict2)
    return merged
