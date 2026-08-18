"""
SEED Platform (TM), Copyright (c) Alliance for Sustainable Energy, LLC, and other contributors.
See also https://github.com/SEED-platform/building-data-utilities/blob/main/LICENSE.md
"""

from __future__ import annotations

from typing import Any

import requests

from building_data_utilities.chunk import chunk
from building_data_utilities.common import Location


class AmazonAPIKeyError(Exception):
    """Your Amazon API Key is either invalid or at its limit."""


def _process_result(result):
    """
    If multiple geolocations are returned, pass invalid indicator of "Ambiguous".

    According to Amazon Location Services API
    MatchScore -> Overall field holds the confidence level of the geocoding result.
    The confidence level is a value between 0.0 and 1.0, where:
    1.0: A perfect match. The service is highly confident that the returned result is the intended location.
    0.75 - 0.99: A strong match, usually correct but possibly with minor differences (e.g., formatting or missing elements).
    0.5 - 0.74: A moderate match. The result is somewhat relevant but may differ in address details, city, or type.
    0.1 - 0.49: A weak match. The returned place is loosely related (e.g., matching only the city name but not the street).
    0.0: No meaningful match (rarely returned, since results with 0 confidence are usually omitted).

    We will accept a confidence level > 0.90 for now
    """
    quality = "Unknown"
    if len(result.get("ResultItems", [])) != 1:
        return {"quality": "Ambiguous"}
    if len(result.get("ResultItems", [])) == 0:
        return {"quality": "No results found"}

    res = result.get("ResultItems")[0]
    matchScore = res.get("MatchScores")
    if matchScore.get("Overall", 0) < 0.90:
        return {"quality": "Less Than 0.90 Confidence"}
    elif matchScore.get("Overall", 0) >= 0.90:
        quality = matchScore.get("Overall")
        long = res.get("Position")[0]
        lat = res.get("Position")[1]
        # just take the first part of the postal code if there's a +4
        postal_code = res.get("Address").get("PostalCode").split("-")[0] if res.get("Address").get("PostalCode") else None
        # reconstruct a full street address from the parts
        street_address = f"{res.get('Address').get('AddressNumber')} {res.get('Address').get('Street')}"

        d = {
            "quality": quality,
            "address": street_address,
            "longitude": long,
            "latitude": lat,
            "postal_code": postal_code,
            "city": res.get("Address").get("Locality"),
            "state": res.get("Address").get("Region", {}).get("Code"),
            "country": res.get("Address").get("Country", {}).get("Code2"),
        }
        return d
    else:
        return {"quality": quality}


def geocode_addresses(
    locations: list[Location], amazon_api_key: str, amazon_base_url: str, amazon_app_id: str | None = None
) -> list[dict[str, Any]]:
    results = []

    # Amazon Location Services is limited to 1 address per request, 100 requests per second
    # The NLR gateway limits access to 1000 per hour.
    # URL example: https://places.geo.us-east-2.api.aws/v2/geocode?api_key
    # NLR URL example: https://developer.nlr.gov/api/tada/amazon-location-service/places/v2/geocode?api_key
    for location_chunk in chunk(locations, chunk_size=1):
        # reformat location chunk to a string list of addresses
        # data that could be in there are: street, city, state, postal_code, country
        # street is required, the rest are optional
        # should at least provide city and state for a good result though
        processed_address = [
            ", ".join(
                part
                for part in [
                    loc.get("street"),
                    loc.get("city", ""),
                    loc.get("state", ""),
                    loc.get("postal_code", ""),
                    loc.get("country", ""),
                ]
                if part
            )
            for loc in location_chunk
        ]
        clean_address = [loc.strip(", ") for loc in processed_address]  # remove any leading/trailing commas
        query_str = "\n".join(clean_address)  # join into a single string with newlines

        url_str = f"{amazon_base_url}/geocode/?api_key={amazon_api_key}"
        if amazon_app_id:
            url_str += f"&_app_id={amazon_app_id}"
        response = requests.post(
            url_str,
            json={
                "QueryText": query_str,
                "IndentedUse": "Storage",
                "options": {
                    "maxResults": 2,
                    "thumbMaps": False,
                },
            },
            verify=True,
        )

        try:
            # Catch invalid API key error before parsing the response
            if response.status_code in [401, 400]:
                raise AmazonAPIKeyError(
                    f"Failed geocoding property states due to Amazon error. API Key is invalid with message: {response.content}."
                )
            if response.status_code == 403:
                raise AmazonAPIKeyError(
                    "Failed geocoding property states due to Amazon error. Your Amazon API Key is either invalid or at its limit."
                )
            results.append(response.json())
        except Exception as e:
            if response.status_code == 403:
                raise AmazonAPIKeyError(
                    "Failed geocoding property states due to Amazon error. Your Amazon API Key is either invalid or at its limit."
                )
            else:
                raise e
    return [_process_result(result) for result in results]
