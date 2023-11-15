# !/usr/bin/env python
# encoding: utf-8
"""
SEED Platform (TM), Copyright (c) Alliance for Sustainable Energy, LLC, and other contributors.
See also https://github.com/seed-platform/seed/main/LICENSE.md
"""
from buildingid.code import decode, encode
from openlocationcode.openlocationcode import MAX_DIGIT_COUNT_
from shapely.geometry import Polygon


def encode_ubid(geometry: Polygon) -> str:
    min_longitude, min_latitude, max_longitude, max_latitude = geometry.bounds
    centroid = geometry.centroid
    ubid = encode(min_latitude, min_longitude, max_latitude, max_longitude, centroid.y, centroid.x, codeLength=MAX_DIGIT_COUNT_)
    return ubid


# Return UBID bounding box as polygon
def decode_ubid(ubid: str) -> Polygon:
    code_area = decode(ubid)
    return Polygon([
        [code_area.longitudeLo, code_area.latitudeHi],
        [code_area.longitudeHi, code_area.latitudeHi],
        [code_area.longitudeHi, code_area.latitudeLo],
        [code_area.longitudeLo, code_area.latitudeLo],
        [code_area.longitudeLo, code_area.latitudeHi],
    ])
