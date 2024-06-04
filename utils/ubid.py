# !/usr/bin/env python
"""
SEED Platform (TM), Copyright (c) Alliance for Sustainable Energy, LLC, and other contributors.
See also https://github.com/SEED-platform/seed/blob/main/LICENSE.md
"""

from buildingid.code import decode, encode
from geopandas import GeoDataFrame
from openlocationcode.openlocationcode import PAIR_CODE_LENGTH_
from shapely.geometry import Point, Polygon


def encode_ubid(geometry: Polygon, code_length: int = PAIR_CODE_LENGTH_) -> str:
    min_longitude, min_latitude, max_longitude, max_latitude = geometry.bounds
    centroid = geometry.centroid
    ubid = encode(min_latitude, min_longitude, max_latitude, max_longitude, centroid.y, centroid.x, codeLength=code_length)
    return ubid


# Return UBID bounding box as polygon
def bounding_box(ubid: str) -> Polygon:
    code_area = decode(ubid)
    return Polygon(
        [
            [code_area.longitudeLo, code_area.latitudeHi],
            [code_area.longitudeHi, code_area.latitudeHi],
            [code_area.longitudeHi, code_area.latitudeLo],
            [code_area.longitudeLo, code_area.latitudeLo],
            [code_area.longitudeLo, code_area.latitudeHi],
        ]
    )


# Return UBID centroid as point
def centroid(ubid: str) -> Point:
    code_area = decode(ubid)
    return Point(code_area.centroid.longitudeCenter, code_area.centroid.latitudeCenter)


def add_ubid_to_geodataframe(
    gdf: GeoDataFrame,
    footprint_column: str = "geometry",
    additional_ubid_columns_to_create: list[str] = ["ubid_centroid", "ubid_bbox"],
) -> GeoDataFrame:
    """Add UBID and related fields to a GeoDataFrame

    Args:
        gdf (GeoDataFrame): Incoming data frame
        footprint_column (str, optional): Where is the footprint polygon defined. Defaults to "geometry".
        additional_ubid_columns_to_create (list[str], optional): Which fields to create.
            Defaults to ['ubid_centroid', 'ubid_bbox'].

    Returns:
        GeoDataFrame: New data frame with UBID and related fields
    """
    # only apply to the fields that have footprints
    filter_str = gdf[footprint_column].notna()

    # make sure the columns are created
    if "ubid" not in gdf.columns:
        gdf["ubid"] = None

    for column in additional_ubid_columns_to_create:
        if column not in gdf.columns:
            gdf[column] = None

    # UBID is always calculated and stored in 'ubid'
    gdf.loc[filter_str, "ubid"] = gdf[filter_str].apply(lambda x: encode_ubid(x[footprint_column]), axis=1)

    if "ubid_centroid" in additional_ubid_columns_to_create:
        gdf.loc[filter_str, "ubid_centroid"] = gdf[filter_str].apply(lambda x: centroid(x["ubid"]), axis=1)

    if "ubid_bbox" in additional_ubid_columns_to_create:
        gdf.loc[filter_str, "ubid_bbox"] = gdf[filter_str].apply(lambda x: bounding_box(x["ubid"]), axis=1)

    return gdf
