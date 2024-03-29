# !/usr/bin/env python
# encoding: utf-8
"""
SEED Platform (TM), Copyright (c) Alliance for Sustainable Energy, LLC, and other contributors.
See also https://github.com/seed-platform/seed/main/LICENSE.md
"""
import gzip
import json
import os
import sys
import warnings
from typing import Any

import geopandas as gpd
import mercantile
import pandas as pd
from dotenv import load_dotenv
from shapely.geometry import Point
from utils.common import Location
from utils.ubid import bounding_box, centroid, encode_ubid
from utils.geocode_addresses import geocode_addresses
from utils.normalize_address import normalize_address
from utils.update_dataset_links import update_dataset_links
from utils.update_quadkeys import update_quadkeys

warnings.filterwarnings('ignore', category=RuntimeWarning)
warnings.filterwarnings('ignore', category=UserWarning)
load_dotenv()


def main():
    MAPQUEST_API_KEY = os.getenv('MAPQUEST_API_KEY')
    if not MAPQUEST_API_KEY:
        sys.exit('Missing MapQuest API key')

    if not os.path.exists('locations.json'):
        sys.exit('Missing locations.json file')

    if not os.path.exists('data/quadkeys'):
        os.makedirs('data/quadkeys')

    with open('locations.json') as f:
        locations: list[Location] = json.load(f)

    for loc in locations:
        loc['street'] = normalize_address(loc['street'])

    data = geocode_addresses(locations, MAPQUEST_API_KEY)

    # TODO confirm high quality geocoding results, and that all results have latitude/longitude properties

    # Find all quadkeys that the coordinates fall within
    quadkeys = set()
    for datum in data:
        tile = mercantile.tile(datum['longitude'], datum['latitude'], 9)
        quadkey = int(mercantile.quadkey(tile))
        quadkeys.add(quadkey)
        datum['quadkey'] = quadkey

    # Download quadkey dataset links
    update_dataset_links()

    # Download quadkeys
    update_quadkeys(list(quadkeys))

    # Loop properties and load quadkeys as necessary
    loaded_quadkeys: dict[int, Any] = {}
    for datum in data:
        quadkey = datum['quadkey']
        if quadkey not in loaded_quadkeys:
            print(f"Loading {quadkey}")

            with gzip.open(f"data/quadkeys/{quadkey}.geojsonl.gz", 'rb') as f:
                loaded_quadkeys[quadkey] = gpd.read_file(f)
                print(f"  {len(loaded_quadkeys[quadkey])} footprints in quadkey")

        geojson = loaded_quadkeys[quadkey]
        point = Point(datum['longitude'], datum['latitude'])
        point_gdf = gpd.GeoDataFrame(crs='epsg:4326', geometry=[point])

        # intersections have `geometry`, `index_right`, and `height`
        intersections = gpd.sjoin(point_gdf, geojson)
        if len(intersections) >= 1:
            footprint = geojson.iloc[intersections.iloc[0].index_right]
            datum['footprint_match'] = 'intersection'
        else:
            footprint = geojson.iloc[geojson.distance(point).sort_values().index[0]]
            datum['footprint_match'] = 'closest'
        datum['geometry'] = footprint.geometry
        datum['height'] = footprint.height if footprint.height != -1 else None

        # Determine UBIDs from footprints
        datum['ubid'] = encode_ubid(datum['geometry'])

    # Save covered building list as csv and GeoJSON
    columns = ['address', 'city', 'state', 'postal_code', 'side_of_street', 'neighborhood', 'county', 'country', 'latitude', 'longitude', 'quality', 'footprint_match', 'height', 'ubid', 'geometry']
    gdf = gpd.GeoDataFrame(data=data, columns=columns)
    gdf.to_csv('data/covered-buildings.csv', index=False)
    gdf.to_file('data/covered-buildings.geojson', driver='GeoJSON')

    # Save a custom GeoJSON with 3 layers: UBID bounding boxes, footprints, then UBID centroids
    bounding_boxes = gpd.GeoDataFrame(data=[{'UBID Bounding Box': datum['address'], 'geometry': bounding_box(datum['ubid'])} for datum in data], columns=['UBID Bounding Box', 'geometry'])
    centroids = gpd.GeoDataFrame(data=[{'UBID Centroid': datum['address'], 'geometry': centroid(datum['ubid'])} for datum in data], columns=['UBID Centroid', 'geometry'])
    gdf_ubid = pd.concat([bounding_boxes, gdf, centroids])
    with open('data/covered-buildings-ubid.geojson', 'w') as f:
        f.write(gdf_ubid.to_json(drop_id=True, na='drop'))


if __name__ == '__main__':
    main()
