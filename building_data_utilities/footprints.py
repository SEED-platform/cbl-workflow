"""
SEED Platform (TM), Copyright (c) Alliance for Sustainable Energy, LLC, and other contributors.
See also https://github.com/SEED-platform/building-data-utilities/blob/main/LICENSE.md
"""

import gzip
import json
import logging
from pathlib import Path

import geopandas as gpd
import mercantile
import numpy as np
import osmnx as ox
import pandas as pd
from shapely.geometry import MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

from .ubid import centroid, encode_ubid

logger = logging.getLogger(__name__)


def get_best_area_crs(gdf: gpd.GeoDataFrame) -> int:
    """
    Select the best CRS for area calculation based on centroid location.
    Returns an EPSG code.
    """
    centroid_point = gdf.geometry.union_all().centroid
    lon, lat = centroid_point.x, centroid_point.y
    # Alaska
    if lat > 50 and lon < -130:
        return 3338  # Alaska Albers Equal Area
    # Hawaii
    if 18 <= lat <= 23 and -162 <= lon <= -154:
        return 3563  # Hawaii Albers Equal Area
    # Contiguous US
    if 24 <= lat <= 50 and -125 <= lon <= -66:
        return 5070  # USA Contiguous Albers Equal Area
    # Fallback: UTM zone based on longitude
    utm_zone = int((lon + 180) / 6) + 1
    is_northern = lat >= 0
    epsg = 32600 + utm_zone if is_northern else 32700 + utm_zone
    return epsg


def get_quadkeys_for_polygon(polygon: Polygon | MultiPolygon) -> list[int]:
    """
    Get quadkeys that intersect with the given polygon.

    For a MultiPolygon, quadkeys are computed per constituent part (using each part's own
    bounding box) rather than the bounding box of the whole geometry. This avoids sweeping
    in unrelated tiles that lie only in the "gap" between disjoint parts (e.g. when the
    input represents several small, widely-separated areas of interest).

    Args:
        polygon: Shapely Polygon or MultiPolygon object

    Returns:
        List of quadkey integers
    """
    try:
        geoms = list(polygon.geoms) if isinstance(polygon, MultiPolygon) else [polygon]

        quadkeys = set()
        for geom in geoms:
            # Create GeoDataFrame for this part of the area of interest
            aoi_gdf = gpd.GeoDataFrame([{"geometry": geom}], crs="EPSG:4326")

            # Get bounds of this part
            bounds = aoi_gdf.bounds.iloc[0]
            minx, miny, maxx, maxy = bounds["minx"], bounds["miny"], bounds["maxx"], bounds["maxy"]

            # Get quadkeys for this part
            for tile in list(mercantile.tiles(minx, miny, maxx, maxy, zooms=9)):
                quadkeys.add(int(mercantile.quadkey(tile)))

        quadkeys_list = list(quadkeys)
        logger.info(f"The input area spans {len(quadkeys_list)} tiles: {quadkeys_list}")

        return quadkeys_list
    except Exception as e:
        logger.error(f"Error getting quadkeys for polygon: {e}")
        raise


def load_ms_footprints(polygon: Polygon, quadkeys: list[int], quadkeys_dir: Path) -> gpd.GeoDataFrame:
    """
    Load Microsoft footprints for the given polygon and quadkeys.

    Args:
        polygon: Shapely Polygon object defining the area of interest
        quadkeys: List of quadkey integers
        quadkeys_dir: Directory containing the downloaded quadkey tile files
            (see update_dataset_links/update_quadkeys)

    Returns:
        GeoDataFrame containing Microsoft footprints
    """
    try:
        # Create GeoDataFrame for the area of interest
        aoi_gdf = gpd.GeoDataFrame([{"geometry": polygon}], crs="EPSG:4326")

        # Load and process Microsoft footprints
        idx = 0
        ms_gdf = gpd.GeoDataFrame()
        loaded_quadkeys = {}

        for quadkey in quadkeys:
            if quadkey not in loaded_quadkeys:
                logger.info(f"Loading quadkey id: {quadkey}")
                quadkey_file = quadkeys_dir / f"{quadkey}.geojsonl.gz"

                if not quadkey_file.exists():
                    logger.warning(f"Quadkey file not found: {quadkey_file}")
                    continue

                try:
                    with gzip.open(quadkey_file, "rb") as f:
                        gdf = gpd.read_file(f)
                        logger.info(f"  Quadkey: {quadkey} has {len(gdf)} footprints")

                        # Filter geometries within the area of interest
                        gdf = gdf[gdf.geometry.within(aoi_gdf.geometry.iloc[0])]
                        logger.info(f"  Quadkey: {quadkey} has {len(gdf)} footprints within the area of interest")

                        # Save the quadkey to be combined later
                        loaded_quadkeys[quadkey] = gdf

                except Exception as e:
                    logger.error(f"Error loading quadkey {quadkey}: {e}")
                    continue

        # Merge the GeoDataFrames
        for loaded_gdf in loaded_quadkeys.values():
            loaded_gdf["id"] = range(idx, idx + len(loaded_gdf))
            idx += len(loaded_gdf)
            ms_gdf = pd.concat([ms_gdf, loaded_gdf], ignore_index=True)

        if len(ms_gdf) == 0:
            logger.warning("No Microsoft footprints found in the area")
            return gpd.GeoDataFrame()

        logger.info(f"Total Microsoft footprints found: {len(ms_gdf)}")
        return ms_gdf

    except Exception as e:
        logger.error(f"Error loading Microsoft footprints: {e}")
        raise


def process_ms_footprints(ms_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Process Microsoft footprints data.

    Args:
        ms_gdf: GeoDataFrame with Microsoft footprints

    Returns:
        Processed GeoDataFrame
    """
    try:
        # Handle -1 heights
        ms_gdf["height"] = ms_gdf["height"].apply(lambda x: x if x != -1 else None)

        # Add UBIDs
        ms_gdf["ubid"] = ms_gdf.apply(lambda x: encode_ubid(x["geometry"]), axis=1)
        ms_gdf["ubid_centroid"] = ms_gdf.apply(lambda x: centroid(x["ubid"]), axis=1)

        # Decompose the ubid_centroid into lat/long
        ms_gdf["longitude"] = ms_gdf["ubid_centroid"].apply(lambda point: point.x)
        ms_gdf["latitude"] = ms_gdf["ubid_centroid"].apply(lambda point: point.y)
        ms_gdf = ms_gdf.drop(columns=["ubid_centroid"])

        # Calculate footprint area using best CRS for the region
        if ms_gdf.crs is None:
            ms_gdf = ms_gdf.set_crs(epsg=4326)
        best_crs = get_best_area_crs(ms_gdf)
        ms_gdf_proj = ms_gdf.to_crs(epsg=best_crs)
        ms_gdf["footprint_area_m2"] = ms_gdf_proj.area
        ms_gdf["footprint_area_ft2"] = ms_gdf["footprint_area_m2"] * 10.764
        # Return to 4326 for further processing
        ms_gdf = ms_gdf.to_crs(epsg=4326)

        # Add address fields in the format expected by the frontend
        ms_gdf["street_address"] = ""
        ms_gdf["city"] = ""
        ms_gdf["state"] = ""
        ms_gdf["postal_code"] = ""
        ms_gdf["country"] = ""

        # Set the source of the data to "Microsoft Footprints"
        ms_gdf["source"] = "Microsoft Footprints"

        logger.info(f"Processed Microsoft footprints: {len(ms_gdf)} final footprints")
        logger.debug(f"Microsoft footprints dtypes: {ms_gdf.dtypes}")
        return ms_gdf

    except Exception as e:
        logger.error(f"Error processing Microsoft footprints: {e}")
        raise


def load_osm_footprints(polygon: Polygon) -> gpd.GeoDataFrame:
    """
    Load OpenStreetMap footprints for the given polygon.

    Args:
        polygon: Shapely Polygon object defining the area of interest

    Returns:
        GeoDataFrame containing OSM footprints
    """
    try:
        # Get OSM footprints
        osm_gdf = ox.features_from_polygon(polygon, tags={"building": True})

        if len(osm_gdf) == 0:
            logger.warning("No OSM footprints found in the area")
            return gpd.GeoDataFrame()

        logger.info(f"Total OSM footprints found: {len(osm_gdf)}")
        return osm_gdf

    except Exception as e:
        logger.error(f"Error loading OSM footprints: {e}")
        raise


def process_osm_footprints(osm_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Process OpenStreetMap footprints data.

    Args:
        osm_gdf: GeoDataFrame with OSM footprints

    Returns:
        Processed GeoDataFrame
    """
    try:
        # Convert to GeoDataFrame if it's not already
        if not isinstance(osm_gdf, gpd.GeoDataFrame):
            osm_gdf = gpd.GeoDataFrame(osm_gdf)

        # Filter out point geometries (we only want polygons)
        osm_gdf = osm_gdf[osm_gdf.geometry.geom_type != "Point"].copy()

        # Reset index to add unique IDs
        osm_gdf = osm_gdf.reset_index()
        osm_gdf["osm_id"] = osm_gdf["id"]
        osm_gdf["id"] = range(len(osm_gdf))

        # Log the columns to help debug
        logger.debug(f"OSM DataFrame columns after reset_index: {osm_gdf.columns.tolist()}")

        # Drop unwanted columns
        drop_cols = ["nodes", "area_right", "centroid", "bounds_minx", "bounds_miny", "bounds_maxx", "bounds_maxy", "ways"]
        drop_cols = [col for col in drop_cols if col in osm_gdf.columns]
        if drop_cols:
            osm_gdf = osm_gdf.drop(columns=drop_cols)

        # Add UBIDs
        osm_gdf["ubid"] = osm_gdf.apply(lambda x: encode_ubid(x["geometry"]), axis=1)
        osm_gdf["ubid_centroid"] = osm_gdf.apply(lambda x: centroid(x["ubid"]), axis=1)

        # Decompose the ubid_centroid into lat/long
        osm_gdf["longitude"] = osm_gdf["ubid_centroid"].apply(lambda point: point.x)
        osm_gdf["latitude"] = osm_gdf["ubid_centroid"].apply(lambda point: point.y)
        osm_gdf = osm_gdf.drop(columns=["ubid_centroid"])

        # Calculate footprint area using best CRS for the region
        if osm_gdf.crs is None:
            osm_gdf = osm_gdf.set_crs(epsg=4326)
        best_crs = get_best_area_crs(osm_gdf)
        osm_gdf_proj = osm_gdf.to_crs(epsg=best_crs)
        osm_gdf["footprint_area_m2"] = osm_gdf_proj.area
        osm_gdf["footprint_area_ft2"] = osm_gdf["footprint_area_m2"] * 10.764
        # Return to 4326 for further processing
        osm_gdf = osm_gdf.to_crs(epsg=4326)

        # Set the source of the data to "OpenStreetMap"
        osm_gdf["source"] = "OpenStreetMap"

        # Add OSM URL - handle different possible column names after reset_index
        def create_url_field(row):
            try:
                # Common patterns after reset_index with OSMnx data
                if "element" in row and "osm_id" in row:
                    return f"https://www.openstreetmap.org/{row['element']}/{row['osm_id']}"
                elif "level_0" in row and "level_1" in row:
                    return f"https://www.openstreetmap.org/{row['level_0']}/{row['level_1']}"
                # Try direct index access if available
                elif hasattr(row, "name") and isinstance(row.name, tuple) and len(row.name) >= 2:
                    return f"https://www.openstreetmap.org/{row.name[0]}/{row.name[1]}"
                # Fallback to generic OSM URL
                else:
                    return "https://www.openstreetmap.org/"
            except Exception as e:
                logger.warning(f"Could not create OSM URL for row: {e}")
                return "https://www.openstreetmap.org/"

        osm_gdf["osm_url"] = osm_gdf.apply(create_url_field, axis=1)

        # Clean up building types
        if "building" in osm_gdf.columns:
            # Remove buildings that are just roofs
            osm_gdf = osm_gdf[osm_gdf["building"] != "roof"]

            # If there is an amenity, then make the building the amenity
            if "amenity" in osm_gdf.columns:
                osm_gdf.loc[osm_gdf["amenity"].notna(), "building"] = osm_gdf["amenity"]

            # Map "yes" buildings to "Unknown"
            osm_gdf.loc[osm_gdf["building"] == "yes", "building"] = "Unknown"

            # save building to building_type
            osm_gdf["building_type"] = osm_gdf["building"]
            # remove building
            osm_gdf = osm_gdf.drop(columns=["building"])

        # Handle height and levels
        if "height" not in osm_gdf.columns:
            osm_gdf["height"] = 0
        else:
            osm_gdf["height"] = osm_gdf["height"].fillna(0)

        if "building:levels" in osm_gdf.columns:
            osm_gdf["building:levels"] = osm_gdf["building:levels"].fillna(0)
            osm_gdf["building:levels"] = osm_gdf["building:levels"].astype(int)

        # Process address fields
        _process_osm_address_fields(osm_gdf)

        logger.info(f"Processed OSM footprints: {len(osm_gdf)} final footprints")
        return osm_gdf

    except Exception as e:
        logger.error(f"Error processing OSM footprints: {e}")
        raise


def _process_osm_address_fields(osm_gdf: gpd.GeoDataFrame) -> None:
    """
    Process address fields for OSM footprints.

    Args:
        osm_gdf: GeoDataFrame to process (modified in place)
    """
    logger.info("Processing address fields...")
    logger.debug(f"OSM DataFrame columns: {osm_gdf.columns.tolist()}")

    # Process address fields
    if "addr:city" not in osm_gdf.columns:
        osm_gdf["city"] = osm_gdf["city"] if "city" in osm_gdf.columns else ""
    else:
        osm_gdf["city"] = osm_gdf["addr:city"].fillna("")

    if "addr:housenumber" not in osm_gdf.columns:
        osm_gdf["addr:housenumber"] = ""
    else:
        osm_gdf["addr:housenumber"] = osm_gdf["addr:housenumber"].fillna("")

    if "addr:street" not in osm_gdf.columns:
        osm_gdf["addr:street"] = ""
    else:
        osm_gdf["addr:street"] = osm_gdf["addr:street"].fillna("")

    # check if addr:housenumber and addr:street are not null
    # if not null, combine them and put in "street_address"
    house_num = osm_gdf["addr:housenumber"].astype(str).str.strip()
    street = osm_gdf["addr:street"].astype(str).str.strip()

    # Create masks for valid values (not empty, not 'nan')
    has_house_num = ~house_num.isin(["", "nan", "None"])
    has_street = ~street.isin(["", "nan", "None"])

    # Use pandas vectorized operations to create street_address
    street_address = street.where(has_street, "")  # use street if available
    street_address = house_num.where(has_house_num & ~has_street, street_address)  # use house_num if no street
    street_address = (house_num + " " + street).where(has_house_num & has_street, street_address)  # combine both if available

    osm_gdf["street_address"] = street_address
    if "addr:state" not in osm_gdf.columns:
        osm_gdf["state"] = ""
    else:
        osm_gdf["state"] = osm_gdf["addr:state"].fillna("")

    if "addr:postcode" not in osm_gdf.columns:
        osm_gdf["postal_code"] = ""
    else:
        osm_gdf["postal_code"] = osm_gdf["addr:postcode"].fillna("")

    # Add country field
    osm_gdf["country"] = ""


def merge_footprint_geodataframes(gdf_1: gpd.GeoDataFrame, gdf_2: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Merge two footprint GeoDataFrames, preserving unique footprints and merging overlapping ones.

    This method:
    1. Identifies overlapping footprints between the two datasets
    2. Merges the overlapping footprints into combined features
    3. Preserves non-overlapping footprints from both datasets
    4. Returns a combined GeoDataFrame with all unique and merged footprints
    5. Clean the fields

    Returns a GeoDataFrame with unique + merged footprints.
    """
    logger.info(f"Starting merge: gdf_1 has {len(gdf_1)} features, gdf_2 has {len(gdf_2)} features")

    # Step 1: Find overlapping footprints
    overlap_gdf = gpd.overlay(gdf_1, gdf_2, how="intersection")
    logger.info(f"Found {len(overlap_gdf)} overlapping footprint pairs")

    if len(overlap_gdf) == 0:
        # No overlaps, just combine all footprints
        logger.info("No overlaps found, combining all footprints as-is")

        # Add source column to identify origin
        gdf_1_copy = gdf_1.copy()
        gdf_2_copy = gdf_2.copy()
        gdf_1_copy["source"] = "Microsoft"
        gdf_2_copy["source"] = "OpenStreetMap"

        # Combine all footprints
        combined_gdf = pd.concat([gdf_1_copy, gdf_2_copy], ignore_index=True)
        logger.info(f"Combined result: {len(combined_gdf)} total footprints")
        return _finalize_footprints(combined_gdf)

    # Step 2: Identify which footprints from each dataset were involved in overlaps
    # Use spatial joins to identify overlapping footprints, since this is more reliable than
    # trying to track indices through overlay.
    spatial_join = gpd.sjoin(gdf_1, gdf_2, how="inner", predicate="intersects")
    overlapping_indices_1 = set(spatial_join.index)
    overlapping_indices_2 = set(spatial_join["index_right"])

    logger.info(f"Overlapping footprints: {len(overlapping_indices_1)} from MS, {len(overlapping_indices_2)} from OSM")

    # Step 3: Process the overlapping footprints

    # Create a mapping for how each column should be aggregated when dissolving
    # "first" means take the first value found for that column in each group
    column_mapping = dict.fromkeys(overlap_gdf.columns, "first")

    # For some columns, we want to aggregate differently:
    # "unique" will collect all unique values in the group (e.g., if multiple heights or UBIDs)
    for unique_col in ["ubid_2", "height_1", "height_2"]:
        if unique_col in overlap_gdf.columns:
            column_mapping[unique_col] = "unique"

    # Remove columns that are used for grouping or are geometry, since those are handled separately
    column_mapping.pop("ubid_1", None)
    column_mapping.pop("geometry", None)

    # Dissolve merges all rows with the same UBID 1 into a single row, combining their geometries
    # and aggregating the other columns according to column_mapping. This is useful for combining
    # overlapping/intersecting footprints that share the same UBID into a single, unified footprint.
    overlap_gdf = overlap_gdf.dissolve(by="ubid_1", aggfunc=column_mapping).reset_index()

    # Now for the unique column_mapping names, rename to make it clear that they
    # are now lists for posterity sake
    for col in column_mapping:
        overlap_gdf = overlap_gdf.rename(columns={col: f"{col}_list" if column_mapping[col] == "unique" else col})

    # For height, merge the height_1 and height_2 lists
    def merge_height_lists(row):
        """Safely merge height lists from both datasets"""
        all_heights = []

        # Collect heights from both columns
        for col in ["height_1_list", "height_2_list"]:
            if col in row and row[col] is not None:
                if isinstance(row[col], (list, tuple)):
                    all_heights.extend([h for h in row[col] if h is not None and str(h) != "nan"])
                elif row[col] is not None and str(row[col]) != "nan":
                    all_heights.append(row[col])

        # Convert to float and remove duplicates
        valid_heights = []
        for h in all_heights:
            try:
                height_val = float(h)
                if height_val > 0:  # Only keep positive heights
                    valid_heights.append(height_val)
            except (ValueError, TypeError):
                continue

        return list(set(valid_heights)) if valid_heights else []

    overlap_gdf["height_list"] = overlap_gdf.apply(merge_height_lists, axis=1)

    # grab the largest height and set to height
    overlap_gdf["height"] = overlap_gdf["height_list"].apply(lambda x: float(max(x)) if x and len(x) > 0 else None)

    # Merge MultiPolygon into a single Polygon if possible
    def merge_or_largest(geom):
        if isinstance(geom, MultiPolygon):
            merged = unary_union(geom)
            if isinstance(merged, Polygon):
                return merged
            else:
                largest_polygon = max(geom.geoms, key=lambda p: p.area)
                return largest_polygon
        return geom

    overlap_gdf["geometry"] = overlap_gdf["geometry"].apply(merge_or_largest)

    # map the building_type to the values in ESPM. X : Y, X = OSM value, Y = ESPM
    # OpenStreetMap values can be found here: https://wiki.openstreetmap.org/wiki/Key:building
    # The "building" values reported in OSM can be spotty and these assumptions can
    # be improved. We also know that many building types are not what we think they
    # are based on community surveys (e.g., libraries are used for more than reading--they
    # are shelters, internet, offices, etc)
    espm_building_types_enum = {
        "civic": "Public services",
        "apartments": "Lodging/residential",
        # placeholders
        "unknown_1": "Banking/financial services",
        "unknown_2": "Education",
        "unknown_3": "Entertainment/public assembly",
        "unknown_4": "Food sales and service",
        "unknown_5": "Healthcare",
        "unknown_6": "Lodging/residential",
        "unknown_7": "Manufacturing/industrial",
        "unknown_8": "Office",
        "unknown_9": "Other",
        "unknown_10": "Public services",
        "unknown_11": "Religious worship",
        "unknown_12": "Retail",
        "unknown_13": "Services",
        "unknown_14": "Technology/science",
        "unknown_15": "Utility",
        "unknown_16": "Warehouse/storage",
    }

    # look up building type, if it isn't found then just use "All"
    # rename old building_type to OSM first
    if "building_type" in overlap_gdf.columns:
        overlap_gdf = overlap_gdf.rename(columns={"building_type": "building_type_osm"})
    else:
        overlap_gdf["building_type_osm"] = "All"
    overlap_gdf["building_type"] = overlap_gdf["building_type_osm"].map(espm_building_types_enum).fillna("All")

    # now recalculate the UBID, floor area, centroid, etc
    overlap_gdf["ubid"] = overlap_gdf.apply(lambda x: encode_ubid(x["geometry"]), axis=1)
    overlap_gdf["ubid_centroid"] = overlap_gdf.apply(lambda x: centroid(x["ubid"]), axis=1)

    # Convert all float columns to native Python float to avoid numpy float64 serialization issues
    for col in overlap_gdf.select_dtypes(include=["float", "float64"]).columns:
        overlap_gdf[col] = overlap_gdf[col].apply(lambda v: float(v) if v is not None else None)

    # Decompose the ubid_centroid into lat/long
    overlap_gdf["longitude"] = overlap_gdf["ubid_centroid"].apply(lambda point: point.x)
    overlap_gdf["latitude"] = overlap_gdf["ubid_centroid"].apply(lambda point: point.y)
    overlap_gdf = overlap_gdf.drop(columns=["ubid_centroid"])

    # Calculate footprint area using best CRS for the region
    if overlap_gdf.crs is None:
        overlap_gdf = overlap_gdf.set_crs(epsg=4326)
    best_crs = get_best_area_crs(overlap_gdf)
    overlap_gdf_proj = overlap_gdf.to_crs(epsg=best_crs)
    overlap_gdf["footprint_area_m2"] = overlap_gdf_proj.area
    overlap_gdf["footprint_area_ft2"] = overlap_gdf["footprint_area_m2"] * 10.764
    # Return to 4326 for further processing
    overlap_gdf = overlap_gdf.to_crs(epsg=4326)

    # calculate the number of stories and gross floor area based on a 3.5 meter height
    overlap_gdf["number_of_stories"] = (overlap_gdf["height"] / 3.5).apply(
        lambda x: int(np.ceil(x)) if x is not None and not np.isnan(x) and x > 0 else 1
    )
    overlap_gdf["gross_floor_area_m2"] = overlap_gdf["footprint_area_m2"] * overlap_gdf["number_of_stories"]
    overlap_gdf["gross_floor_area_ft2"] = overlap_gdf["gross_floor_area_m2"] * 10.764

    # Mark merged footprints as 'Merged' source
    overlap_gdf["source"] = "Merged"
    logger.info(f"Processed {len(overlap_gdf)} merged footprints")

    # Step 4: Get non-overlapping footprints from each dataset
    non_overlapping_1 = gdf_1.loc[~gdf_1.index.isin(overlapping_indices_1)].copy()
    non_overlapping_2 = gdf_2.loc[~gdf_2.index.isin(overlapping_indices_2)].copy()

    # Add source labels
    non_overlapping_1["source"] = "Microsoft"
    non_overlapping_2["source"] = "OpenStreetMap"

    logger.info(f"Non-overlapping: {len(non_overlapping_1)} from MS, {len(non_overlapping_2)} from OSM")

    # Step 5: Combine all footprints (merged + unique from both datasets)
    all_parts = []

    if len(overlap_gdf) > 0:
        all_parts.append(overlap_gdf)
    if len(non_overlapping_1) > 0:
        all_parts.append(non_overlapping_1)
    if len(non_overlapping_2) > 0:
        all_parts.append(non_overlapping_2)

    if not all_parts:
        # Edge case: no footprints at all
        logger.info("No footprints to return")
        return gpd.GeoDataFrame()

    # Combine all parts
    combined_gdf = pd.concat(all_parts, ignore_index=True, sort=False)
    logger.info(
        f"Final result: {len(combined_gdf)} total footprints "
        f"({len(overlap_gdf)} merged + {len(non_overlapping_1)} MS unique + {len(non_overlapping_2)} OSM unique)"
    )

    # clean-up. there are multiple duplicate fields with _1 and _2 in the combined_gdf, delete them all
    cols_to_drop = [col for col in combined_gdf.columns if col.endswith(("_1", "_2"))]
    combined_gdf = combined_gdf.drop(columns=cols_to_drop)

    # if street_address is empty, use Addr:househumber and Addr:street to create it
    if "street_address" in combined_gdf.columns:
        empty_street_mask = combined_gdf["street_address"].isna() | (combined_gdf["street_address"].str.strip() == "")
        if empty_street_mask.any():
            house_numbers = (
                combined_gdf.loc[empty_street_mask, "addr:housenumber"].astype(str).str.strip()
                if "addr:housenumber" in combined_gdf.columns
                else ""
            )
            streets = (
                combined_gdf.loc[empty_street_mask, "addr:street"].astype(str).str.strip()
                if "addr:street" in combined_gdf.columns
                else ""
            )

            street_addresses = []
            for house_num, street_name in zip(house_numbers, streets):
                if house_num and house_num != "nan" and street_name and street_name != "nan":
                    street_addresses.append(f"{house_num} {street_name}")
                elif street_name and street_name != "nan":
                    street_addresses.append(street_name)
                elif house_num and house_num != "nan":
                    street_addresses.append(house_num)
                else:
                    street_addresses.append("")

            combined_gdf.loc[empty_street_mask, "street_address"] = street_addresses

    # if city is empty:
    # use addr:city to fill it. same with state and addr:state and postal_code and addr:postcode
    for field, addr_field in [("city", "addr:city"), ("state", "addr:state"), ("postal_code", "addr:postcode")]:
        if field in combined_gdf.columns and addr_field in combined_gdf.columns:
            empty_mask = combined_gdf[field].isna() | (combined_gdf[field].str.strip() == "")
            if empty_mask.any():
                combined_gdf.loc[empty_mask, field] = combined_gdf.loc[empty_mask, addr_field].fillna("")

    # These fields also need to be cleaned up:
    # Height 1 List, Height 2 List, Height List, Id1, Id2, Latitude 1, Latitude 2, Longitude 1, Longitude 2, OSM_ID 1, OSM_ID 2, UBID 1, UBID 2
    # Street Address 1, Street Address 2, City 1, City 2, Postal Code 1, Postal Code 2, State 1, State 2
    # Source 1, Source 2, State 1, State 2, Street Address 2, Ubid 1, Ubid 2, Ubid 1 List, Ubid 2 List
    cleanup_cols = [
        "addr:city",
        "addr:housenumber",
        "addr:postcode",
        "addr:state",
        "addr:street",
        "Addr:streetcity_1",
        "city_2",
        "country_1",
        "country_2",
        "footprint_area_ft2_1",
        "footprint_area_ft2_2",
        "footprint_area_m2_1",
        "footprint_area_m2_2",
        "gross_floor_area_ft2_1",
        "gross_floor_area_ft2_2",
        "gross_floor_area_m2_1",
        "gross_floor_area_m2_2",
        "height_1_list",
        "height_2_list",
        "height_list",
        "id_1",
        "id_2",
        "latitude_1",
        "latitude_2",
        "longitude_1",
        "longitude_2",
        "osm_id_1",
        "osm_id_2",
        "postal_code_1",
        "postal_code_2",
        "state_1",
        "state_2",
        "source_1",
        "source_2",
        "street_address_1",
        "street_address_2",
        "ubid_1",
        "ubid_2",
        "ubid_1_list",
        "ubid_2_list",
    ]
    cleanup_cols = [col for col in cleanup_cols if col in combined_gdf.columns]  # only keep existing columns
    combined_gdf = combined_gdf.drop(columns=cleanup_cols)

    # also remove all Addr:* fields if they exist
    addr_cols = [col for col in combined_gdf.columns if col.startswith("Addr:")]
    combined_gdf = combined_gdf.drop(columns=addr_cols)

    return _finalize_footprints(combined_gdf)


def build_point_query_polygon(points: list[dict], buffer_degrees: float = 0.003) -> Polygon | MultiPolygon:
    """
    Build a small, padded box around EACH query point and return their union, suitable for
    looking up nearby MS/OSM footprints (via get_quadkeys_for_polygon/load_*_footprints).

    A per-point box (rather than one bounding box spanning every point) is used so that
    selecting points that are geographically far apart doesn't sweep in the entire
    (potentially huge/unrelated) area between them.

    Args:
        points: List of dicts with "latitude" and "longitude" keys
        buffer_degrees: Padding (in degrees) added around each point, to ensure footprints
            near (but not exactly centered on) the point are captured

    Returns:
        Shapely Polygon (single point) or MultiPolygon (multiple points) covering the area
        around each point plus padding
    """
    boxes = [
        box(
            float(p["longitude"]) - buffer_degrees,
            float(p["latitude"]) - buffer_degrees,
            float(p["longitude"]) + buffer_degrees,
            float(p["latitude"]) + buffer_degrees,
        )
        for p in points
    ]
    return unary_union(boxes)


def match_points_to_ms_footprints(points: list[dict], quadkeys_dir: Path) -> dict[int, dict]:
    """
    Batched matching of a (potentially large) list of geocoded points to Microsoft footprints,
    grouped and spatial-joined per quadkey tile instead of one `gpd.sjoin` call per individual
    point.

    Args:
        points: list of dicts, each with "index" (the point's position in the caller's
            data list), "latitude", and "longitude" keys.
        quadkeys_dir: Directory containing the downloaded quadkey tile files

    Returns:
        Dict mapping each input point's "index" to a result dict with keys:
        "geometry" (shapely geometry), "height" (float | None), "ubid" (str),
        "footprint_match" ("intersection" | "closest"). Points whose quadkey tile file
        is missing/unreadable, or that have no candidate footprints at all, are omitted.
    """
    if not points:
        return {}

    # Group points by MS quadkey tile (zoom 9) so each tile file is loaded/read once and
    # matched against all of its points in a single vectorized spatial join.
    points_by_quadkey: dict[int, list[dict]] = {}
    for p in points:
        tile = mercantile.tile(float(p["longitude"]), float(p["latitude"]), 9)
        quadkey = int(mercantile.quadkey(tile))
        points_by_quadkey.setdefault(quadkey, []).append(p)

    results: dict[int, dict] = {}

    for quadkey, quadkey_points in points_by_quadkey.items():
        quadkey_file = quadkeys_dir / f"{quadkey}.geojsonl.gz"
        if not quadkey_file.exists():
            logger.warning(f"Quadkey file not found: {quadkey_file}")
            continue

        try:
            with gzip.open(quadkey_file, "rb") as f:
                footprints_gdf = gpd.read_file(f)
        except Exception as e:
            logger.error(f"Error loading quadkey {quadkey}: {e}")
            continue

        if len(footprints_gdf) == 0:
            continue

        points_gdf = gpd.GeoDataFrame(
            {"point_index": [p["index"] for p in quadkey_points]},
            geometry=[Point(float(p["longitude"]), float(p["latitude"])) for p in quadkey_points],
            crs="EPSG:4326",
        )

        # Single vectorized join for every point in this tile, instead of one join per point.
        joined = gpd.sjoin(points_gdf, footprints_gdf, predicate="within", how="left")
        joined = joined[~joined.index.duplicated(keep="first")]

        unmatched_indices = []
        for row in joined.itertuples():
            point_index = row.point_index
            footprint_idx = getattr(row, "index_right", None)
            if footprint_idx is None or (isinstance(footprint_idx, float) and pd.isna(footprint_idx)):
                unmatched_indices.append(point_index)
                continue

            footprint = footprints_gdf.iloc[int(footprint_idx)]
            results[point_index] = {
                "geometry": footprint.geometry,
                "height": footprint.height if footprint.height != -1 else None,
                "ubid": encode_ubid(footprint.geometry),
                "footprint_match": "intersection",
            }

        # Points with no intersecting footprint fall back to nearest-by-distance within
        # the same tile (still one vectorized distance computation per remaining point,
        # not a fresh sjoin).
        if unmatched_indices:
            point_by_index = {p["index"]: p for p in quadkey_points}
            for point_index in unmatched_indices:
                p = point_by_index[point_index]
                point_geom = Point(float(p["longitude"]), float(p["latitude"]))
                nearest_idx = footprints_gdf.distance(point_geom).sort_values().index[0]
                footprint = footprints_gdf.iloc[nearest_idx]
                results[point_index] = {
                    "geometry": footprint.geometry,
                    "height": footprint.height if footprint.height != -1 else None,
                    "ubid": encode_ubid(footprint.geometry),
                    "footprint_match": "closest",
                }

    return results


def match_footprints_to_points(
    points_gdf: gpd.GeoDataFrame, footprints_gdf: gpd.GeoDataFrame, max_nearest_distance_degrees: float = 0.003
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """
    Split a set of candidate footprints into those that match at least one of the given
    query points, and those that don't.

    A footprint "matches" a point either by containment (the point falls inside the
    footprint polygon -- the common case for a geocoded/rooftop-accurate point) or, for any
    point left unmatched by containment, by nearest-distance fallback (mirroring
    match_points_to_ms_footprints()), so points whose coordinates are slightly off from the
    footprint (e.g. geocoded to a nearby location) still get a footprint attached instead of
    silently returning nothing.

    Args:
        points_gdf: GeoDataFrame of query points with a "point_id" column
        footprints_gdf: GeoDataFrame of candidate footprint polygons
        max_nearest_distance_degrees: Maximum distance (in degrees) a point may be from its
            nearest footprint to still count as a "closest" match; prevents matching a point
            to a footprint from a completely unrelated building far away.

    Returns:
        Tuple of (matched, unmatched) GeoDataFrames. `matched` has an added
        "matched_point_id" column identifying which point each footprint overlaps
        (the first matching point, if more than one), and a "footprint_match" column
        ("intersection" or "closest").
    """
    if len(footprints_gdf) == 0:
        return footprints_gdf.copy(), footprints_gdf.copy()

    joined = gpd.sjoin(footprints_gdf, points_gdf[["point_id", "geometry"]], predicate="contains", how="left")

    matched_mask = joined["point_id"].notna()
    matched = joined[matched_mask].copy()
    matched = matched[~matched.index.duplicated(keep="first")]
    matched = matched.rename(columns={"point_id": "matched_point_id"})
    if "index_right" in matched.columns:
        matched = matched.drop(columns=["index_right"])
    matched["footprint_match"] = "intersection"

    unmatched = footprints_gdf.drop(index=matched.index, errors="ignore").copy()

    # Fallback: any query point that didn't fall inside a footprint (e.g. its coordinates
    # are slightly off from the actual rooftop) still gets the nearest remaining footprint,
    # as long as it's within max_nearest_distance_degrees.
    matched_point_ids = set(matched["matched_point_id"]) if len(matched) > 0 else set()
    unmatched_points = points_gdf[~points_gdf["point_id"].isin(matched_point_ids)]

    if len(unmatched_points) > 0 and len(unmatched) > 0:
        closest_rows = []
        remaining = unmatched.copy()
        for _, point_row in unmatched_points.iterrows():
            if len(remaining) == 0:
                break
            distances = remaining.distance(point_row.geometry)
            nearest_idx = distances.sort_values().index[0]
            if distances[nearest_idx] > max_nearest_distance_degrees:
                continue
            nearest_footprint = remaining.loc[[nearest_idx]].copy()
            nearest_footprint["matched_point_id"] = point_row["point_id"]
            nearest_footprint["footprint_match"] = "closest"
            closest_rows.append(nearest_footprint)
            # Don't match the same footprint to more than one point.
            remaining = remaining.drop(index=nearest_idx)

        if closest_rows:
            closest_matched = pd.concat(closest_rows)
            matched = pd.concat([matched, closest_matched])
            unmatched = unmatched.drop(index=closest_matched.index, errors="ignore")

    return matched, unmatched


def footprints_to_feature_dicts(gdf: gpd.GeoDataFrame) -> list[dict]:
    """
    Convert a footprints GeoDataFrame into a list of plain GeoJSON Feature dicts
    (geometry + properties), with NumPy types converted to native Python types.

    Args:
        gdf: GeoDataFrame to convert

    Returns:
        List of GeoJSON Feature dicts (empty list if gdf is empty)
    """
    if len(gdf) == 0:
        return []

    finalized = _finalize_footprints(gdf.copy())
    return json.loads(finalized.to_json())["features"]


def _finalize_footprints(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Apply final processing to footprints for JSON serialization.
    """
    if len(gdf) == 0:
        return gdf

    # Convert all remaining NumPy types to native Python types for JSON serialization
    for col in gdf.columns:
        if col != "geometry":  # Skip geometry column
            gdf[col] = gdf[col].apply(_convert_to_json_serializable)

    # Additional cleanup: ensure all numeric columns are properly converted
    for col in gdf.select_dtypes(include=[np.number]).columns:
        if col != "geometry":
            gdf[col] = gdf[col].astype(float).astype(object)

    # Final check: convert any remaining problematic types
    for col in gdf.columns:
        if col != "geometry":
            try:
                # Test if the column can be JSON serialized
                json.dumps(gdf[col].iloc[0] if len(gdf) > 0 else None)
            except TypeError:
                # Force conversion of problematic values
                gdf[col] = gdf[col].apply(lambda x: str(x) if x is not None else None)

    logger.debug(f"Finalized footprints dtypes: {gdf.dtypes}")

    return gdf


def _convert_to_json_serializable(value):
    """Convert NumPy types and other non-JSON-serializable types to native Python types."""
    # Handle None first
    if value is None:
        return None
    # Handle numpy arrays first (before pd.isna check which fails on arrays)
    elif isinstance(value, (pd.Series, np.ndarray)):
        return value.tolist()
    elif isinstance(value, list):
        return [_convert_to_json_serializable(item) for item in value]
    # Check for pandas NA values safely
    else:
        # First try pd.isna check, but handle arrays gracefully
        try:
            if pd.isna(value):
                return None
        except (ValueError, TypeError):
            # If pd.isna fails (e.g., on complex types), continue to other checks
            pass

        # Handle numpy scalar types
        if isinstance(value, (np.integer, np.int64, np.int32, np.int16, np.int8)):
            return int(value)
        elif isinstance(value, (np.floating, np.float64, np.float32, np.float16)):
            return float(value)
        elif isinstance(value, np.bool_):
            return bool(value)
        elif hasattr(value, "item"):  # Handle numpy scalars
            return value.item()
        else:
            # Force conversion of any remaining pandas/numpy types
            try:
                if hasattr(value, "dtype"):
                    if "int" in str(value.dtype):
                        return int(value)
                    elif "float" in str(value.dtype):
                        return float(value)
                    elif "bool" in str(value.dtype):
                        return bool(value)
            except Exception as e:
                logger.error(f"Exception during conversion to json serializable. logging error: {e}")
            # return value as is
            return value
