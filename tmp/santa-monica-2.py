import contextlib
import math
import warnings

import geopandas as gpd
import pandas as pd
import usaddress
from shapely import wkt, Point

warnings.filterwarnings("ignore", category=UserWarning)

santa_monica = pd.read_csv('data/Santa Monica Covered Buildings.csv')
costar = pd.read_excel('data/OUO_Santa Monica All.xlsx')

footprints = [wkt.loads(x) for x in list(pd.read_excel('data/Santa Monica Footprints.xlsx')['geometry'])]
footprints_gdf = gpd.GeoDataFrame(crs="epsg:4326", geometry=footprints)

existing_costar_ids = set(map(int, santa_monica['CoStar ID'].dropna()))

costar_50k = costar[costar['RBA'] >= 50000]
missing_properties = costar_50k[~costar_50k['Building Status'].isin(['Demolished']) & ~costar_50k['PropertyID'].isin(set(costar_50k['PropertyID']) - existing_costar_ids)]

for i, row in missing_properties.iterrows():
    with contextlib.suppress(TypeError):
        owner_address, _ = usaddress.tag(row['Owner City State Zip'])

    new_row = pd.DataFrame([{
        'Assessor Gross Floor Area': row['RBA'],
        'Primary Property Type EPA Calculated': row['PropertyType'],
        'Address Type': 'building',
        'Street Address': row['Property Address'],
        'City': row['City'],
        'State Abbreviation': row['State'],
        'Postal Code': row['Zip'],
        'Address Type.1': 'owner',
        'Name': row['Owner Name'],
        'Street': row['Owner Address'],
        'City.1': owner_address.get('PlaceName', ''),
        'State Abbreviation.1': owner_address.get('StateName', ''),
        'Postal Code.1': owner_address.get('ZipCode', ''),
        'CoStar ID': row['PropertyID'],
        'CoStar Address': row['Property Address'],
        'Notes': 'Added missing costar address',
    }], columns=santa_monica.columns)
    santa_monica = pd.concat([santa_monica, new_row], ignore_index=True)

# Add lat/long
santa_monica['Latitude'] = None
santa_monica['Longitude'] = None
santa_monica['Footprint Match'] = None
santa_monica['Footprint'] = None

projected_crs = 'EPSG:32610'

for i, row in santa_monica.iterrows():
    costar_id = santa_monica['CoStar ID'][i]
    if not math.isnan(costar_id):
        costar_id = int(costar_id)
        costar_property = costar[costar['PropertyID'] == costar_id].iloc[0]
        santa_monica.at[i, 'Latitude'] = costar_property['Latitude']
        santa_monica.at[i, 'Longitude'] = costar_property['Longitude']

        point = Point(costar_property['Longitude'], costar_property['Latitude'])
        point_gdf = gpd.GeoDataFrame(crs="epsg:4326", geometry=[point])
        intersections = gpd.sjoin(point_gdf, footprints_gdf)
        if len(intersections) >= 1:
            santa_monica.at[i, 'Footprint'] = footprints_gdf.iloc[intersections.iloc[0].index_right].iloc[0].wkt
            santa_monica.at[i, 'Footprint Match'] = "Intersection"
        else:
            santa_monica.at[i, 'Footprint'] = footprints_gdf.iloc[footprints_gdf.distance(point).idxmin()].iloc[0].wkt
            santa_monica.at[i, 'Footprint Match'] = "Closest"

santa_monica.to_excel('data/Santa Monica Covered Buildings with Missing Data.xlsx', index=False)
