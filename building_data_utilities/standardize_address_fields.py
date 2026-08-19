"""
SEED Platform (TM), Copyright (c) Alliance for Sustainable Energy, LLC, and other contributors.
See also https://github.com/SEED-platform/building-data-utilities/blob/main/LICENSE.md
"""

from .normalize_state import normalize_state


def standardize_address_fields(data: list[dict]) -> list[dict]:
    """
    Standardize address field names across all records.

    Args:
        data: List of dictionaries with potentially inconsistent field names

    Returns:
        List of dictionaries with standardized field names
    """
    standardized_data = []

    for record in data:
        standardized = {}

        for key, value in record.items():
            # Standardize common field variations
            lower_key = key.lower()
            if lower_key in ["street_address", "street_addr", "address"]:
                standardized["street_address"] = value
            elif lower_key in ["city", "municipality"]:
                standardized["city"] = value
            elif lower_key in ["state", "province", "region"]:
                standardized["state"] = normalize_state(str(value)) if value else ""
            elif lower_key in ["zip", "zipcode", "postal_code", "postcode"]:
                standardized["postal_code"] = value
            elif lower_key in ["country", "nation"]:
                standardized["country"] = value
            else:
                # Keep other fields as-is
                standardized[key] = value

        standardized_data.append(standardized)

    return standardized_data
