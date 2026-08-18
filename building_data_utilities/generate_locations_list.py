"""
SEED Platform (TM), Copyright (c) Alliance for Sustainable Energy, LLC, and other contributors.
See also https://github.com/SEED-platform/building-data-utilities/blob/main/LICENSE.md
"""

from .common import Location
from .normalize_state import normalize_state


def _extract_field(record: dict, field_name: str) -> str | None:
    """
    Extract field value with case-insensitive matching.

    Args:
        record: Dictionary to search
        field_name: Field name to find

    Returns:
        Field value or None if not found
    """
    for key, value in record.items():
        if key.lower() == field_name.lower():
            return str(value) if value is not None else None
    return None


def generate_locations_list(json_dict_list: list[dict]) -> list[Location]:
    """
    Generate a list of Location objects from user input data.

    Args:
        json_dict_list: List of dictionaries containing location data

    Returns:
        List of Location objects
    """
    locations: list[Location] = []

    for record in json_dict_list:
        street = _extract_field(record, "street_address")
        city = _extract_field(record, "city")
        state = _extract_field(record, "state")

        # Normalize state if needed
        if state:
            state = normalize_state(state)

        loc_dict = {"street": street or "", "city": city or "", "state": state or ""}
        locations.append(loc_dict)

    return locations
