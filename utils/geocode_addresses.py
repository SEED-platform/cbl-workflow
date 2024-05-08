# !/usr/bin/env python
"""
SEED Platform (TM), Copyright (c) Alliance for Sustainable Energy, LLC, and other contributors.
See also https://github.com/seed-platform/seed/main/LICENSE.md
"""

import requests

from utils.chunk import chunk
from utils.common import Location


class MapQuestAPIKeyError(Exception):
    """Your MapQuest API Key is either invalid or at its limit."""


def _process_result(result):
    """
    If multiple geolocations are returned, pass invalid indicator of "Ambiguous".

    According to MapQuest API
     - https://developer.mapquest.com/documentation/geocoding-api/quality-codes/
     GeoCode Quality ratings are provided in 5 characters in the form 'ZZYYY'.
     'ZZ' describes granularity level, and 'YYY' describes confidence ratings.

    Accuracy to either a point or a street address is accepted, while confidence
    ratings must all be at least A's and B's without C's or X's (N/A).
    """
    if len(result.get("locations")) != 1:
        return {"quality": "Ambiguous"}

    quality = result.get("locations")[0].get("geocodeQualityCode")
    granularity_level = quality[0:2]
    confidence_level = quality[2:5]
    is_acceptable_granularity = granularity_level in ["P1", "L1"]
    is_acceptable_confidence = not ("C" in confidence_level or "X" in confidence_level)

    if is_acceptable_confidence and is_acceptable_granularity:
        long = result.get("locations")[0].get("displayLatLng").get("lng")
        lat = result.get("locations")[0].get("displayLatLng").get("lat")

        # flatten out the "adminArea" fields that exist in the result
        admin_areas = {}
        for i in range(1, 7):
            if result.get("locations")[0].get(f"adminArea{i}Type") is None:
                continue
            admin_areas[result.get("locations")[0].get(f"adminArea{i}Type").lower()] = result.get("locations")[0].get(f"adminArea{i}")

        return {
            "quality": quality,
            "address": result.get("locations")[0].get("street"),
            "longitude": long,
            "latitude": lat,
            "postal_code": result.get("locations")[0].get("postalCode"),
            "side_of_street": result.get("locations")[0].get("sideOfStreet"),
        } | admin_areas
    else:
        return {"quality": quality}


def geocode_addresses(locations: list[Location], mapquest_api_key: str):
    # Alternatively, use GeoPandas: https://geopandas.org/en/stable/docs/reference/api/geopandas.tools.geocode.html
    results = []

    # MapQuest is limited to 100 locations per request
    for location_chunk in chunk(locations):
        response = requests.post(
            f"https://www.mapquestapi.com/geocoding/v1/batch?key={mapquest_api_key}",
            json={
                "locations": location_chunk,
                "options": {
                    "maxResults": 2,
                    "thumbMaps": False,
                },
            },
        )

        try:
            # Catch invalid API key error before parsing the response
            if response.status_code == 401:
                raise MapQuestAPIKeyError(
                    "Failed geocoding property states due to MapQuest error. " "API Key is invalid with message: {response.content}."
                )
            results += response.json().get("results")
        except Exception as e:
            if response.status_code == 403:
                raise MapQuestAPIKeyError(
                    "Failed geocoding property states due to MapQuest error. " "Your MapQuest API Key is either invalid or at its limit."
                )
            else:
                raise e

    return [_process_result(result) for result in results]
