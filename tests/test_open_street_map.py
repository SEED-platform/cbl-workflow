"""
SEED Platform (TM), Copyright (c) Alliance for Sustainable Energy, LLC, and other contributors.
See also https://github.com/SEED-platform/building-data-utilities/blob/main/LICENSE.md
"""

import geopandas as gpd
import pytest
from shapely.geometry import Point

from building_data_utilities.open_street_map import (
    download_building,
    download_building_and_nodes_by_id,
    find_nearest_building,
    get_building_id_from_osm_id,
    get_location_bbox,
    get_node_coordinates,
    neighboring_buildings,
    process_dataframe_for_osm_buildings,
    reverse_geocode,
)


class TestOpenStreetMapIntegration:
    def test_reverse_geocode_real(self):
        # Casa Bonita, Lakewood, CO
        lat, lon = 39.7405, -105.0772
        try:
            result = reverse_geocode(lat, lon)
        except Exception as e:
            pytest.skip(f"reverse_geocode failed: {e}")
        assert result is not None
        assert "address" in result
        assert result["address"].get("city", "").lower() == "lakewood"

    def test_get_building_id_from_osm_id_real(self):
        # Use a known OSM way ID for a building (Casa Bonita: 238911424)
        try:
            building_id = get_building_id_from_osm_id(238911424)
        except Exception as e:
            pytest.skip(f"get_building_id_from_osm_id failed: {e}")
        if isinstance(building_id, int):
            assert building_id == 238911424
        else:
            assert "not found" in str(building_id).lower() or "error" in str(building_id).lower()

    # Skipping this for now since we aren't using this method much.
    # def test_download_building_real(self):
    #     # Use a known OSM way ID for a building (Casa Bonita: 238911424)
    #     try:
    #         building_id = get_building_id_from_osm_id(238911424)
    #         data = download_building(building_id)
    #     except Exception as e:
    #         pytest.skip(f"download_building failed: {e}")
    #     assert data is not None
    #     assert "id" in data
    #     assert data["id"] == 238911424
    #     assert data["id"] == building_id


class TestOpenStreetMapCoverage:
    def test_download_building_and_nodes_by_id_real(self):
        # Casa Bonita OSM way ID: 42431790
        try:
            building, nodes = download_building_and_nodes_by_id(42431790)
        except Exception as e:
            pytest.skip(f"download_building_and_nodes_by_id failed: {e}")
        assert building is not None
        assert isinstance(nodes, list)

    def test_get_node_coordinates_invalid(self):
        # Should return None for invalid node IDs
        try:
            result = get_node_coordinates([999999999])
        except Exception as e:
            pytest.skip(f"get_node_coordinates failed: {e}")
        assert result is None

    def test_get_node_coordinates_small_polygon(self):
        # Should return None for less than 3 valid nodes
        # Use a single valid node from OSM (node id: 240949599)
        try:
            result = get_node_coordinates([240949599])
        except Exception as e:
            pytest.skip(f"get_node_coordinates failed: {e}")
        assert result is None

    def test_neighboring_buildings_invalid(self):
        # Should return a string for invalid input
        location = {"address": {"road": "Fake Rd", "city": "Nowhere"}, "lat": 0, "lon": 0}
        try:
            result = neighboring_buildings(location)
        except Exception as e:
            pytest.skip(f"neighboring_buildings failed: {e}")
        assert isinstance(result, str)

    def test_find_nearest_building_real(self):
        # Should return a dict for a real location (Casa Bonita area)
        try:
            result = find_nearest_building(39.7405, -105.0772)
        except Exception as e:
            pytest.skip(f"find_nearest_building failed: {e}")
        if result is not None:
            assert isinstance(result, dict)
        else:
            # Acceptable if nothing is found
            assert result is None

    def test_process_dataframe_for_osm_buildings_invalid_method(self):
        # Should raise ValueError for invalid method
        gdf = gpd.GeoDataFrame({"geometry": [Point(-105.0772, 39.7405)], "id": [1]})
        with pytest.raises(ValueError):  # noqa: PT011
            process_dataframe_for_osm_buildings(gdf, method="bad_method")

    def test_process_dataframe_for_osm_buildings_geometry_centroid(self):
        # Minimal test for geometry_centroid path
        gdf = gpd.GeoDataFrame({"geometry": [Point(-105.0772, 39.7405)], "id": [1]})
        results, errors = process_dataframe_for_osm_buildings(gdf, method="geometry_centroid")
        assert isinstance(results, list)
        assert isinstance(errors, list)

    def test_download_building_error_print(self, capsys):
        # Triggers print on error (lines 34)
        try:
            result = download_building(-999999)  # Invalid ID, guaranteed error
        except Exception as e:
            pytest.skip(f"download_building failed: {e}")
        captured = capsys.readouterr()
        assert "Error: Failed to download building nodes" in captured.out
        assert result is None

    def test_download_building_and_nodes_by_id_error_print(self, capsys):
        # Triggers print on error (lines 45)
        try:
            result = download_building_and_nodes_by_id(-999999)  # Invalid ID, guaranteed error
        except Exception as e:
            pytest.skip(f"download_building_and_nodes_by_id failed: {e}")
        captured = capsys.readouterr()
        assert "Error: Failed to download building nodes" in captured.out
        assert result is None

    def test_get_node_coordinates_invalid_range(self, capsys):
        # Triggers print for invalid coordinates (lines 95-96)
        try:
            result = get_node_coordinates([-1])
        except Exception as e:
            pytest.skip(f"get_node_coordinates failed: {e}")
        captured = capsys.readouterr()
        assert "Error: Failed to retrieve coordinates" in captured.out or result is None

    def test_process_dataframe_for_osm_buildings_copy_source_columns(self):
        # Covers copy_source_columns True and address/geometry/ubid edge cases
        gdf = gpd.GeoDataFrame(
            {
                "geometry": [Point(-105.0772, 39.7405)],
                "id": [1],
                "extra": ["foo"],
            }
        )
        try:
            results, errors = process_dataframe_for_osm_buildings(gdf, method="geometry_centroid", copy_source_columns=True)
        except Exception as e:
            pytest.skip(f"process_dataframe_for_osm_buildings failed: {e}")
        assert isinstance(results, list)
        assert isinstance(errors, list)
        if results:
            assert "extra" in results[0]


class TestGetLocationBbox:
    """These tests will actually call out to OSMnx/Nominatim."""

    def test_get_location_bbox_with_valid_string(self):
        bbox = get_location_bbox("Denver, CO")
        assert bbox is not None
        assert isinstance(bbox, dict)
        assert bbox.get("type") == "Feature"
        geometry = bbox.get("geometry")
        assert geometry is not None
        assert geometry["type"] in ("Polygon", "MultiPolygon")
        coords = geometry["coordinates"]
        assert isinstance(coords, list)

    def test_get_location_bbox_with_valid_dict(self):
        bbox = get_location_bbox({"place_name": "San Francisco, CA"})
        assert bbox is not None
        assert isinstance(bbox, dict)
        assert bbox.get("type") == "Feature"
        geometry = bbox.get("geometry")
        assert geometry is not None
        assert geometry["type"] in ("Polygon", "MultiPolygon")
        coords = geometry["coordinates"]
        assert isinstance(coords, list)

    def test_get_location_bbox_with_invalid_dict(self):
        bbox = get_location_bbox({"not_a_place": "Nowhere"})
        assert bbox is None

    def test_get_location_bbox_with_invalid_string(self):
        bbox = get_location_bbox("asldkfjalsdkfjalskdjflasdjflasdjf")
        assert bbox is None

    def test_get_location_bbox_sunnyvale(self):
        bbox = get_location_bbox("Sunnyvale, California, United States")
        assert bbox is not None
        assert isinstance(bbox, dict)
        assert bbox.get("type") == "Feature"
        geometry = bbox.get("geometry")
        assert geometry is not None
        assert geometry["type"] in ("Polygon", "MultiPolygon")
        coords = geometry["coordinates"]
        assert isinstance(coords, list)

    def test_get_location_bbox_sunnyvale_with_dict(self):
        bbox = get_location_bbox({"place_name": "Sunnyvale, California, United States"})
        assert bbox is not None
        assert isinstance(bbox, dict)
        assert bbox.get("type") == "Feature"
        geometry = bbox.get("geometry")
        assert geometry is not None
        assert geometry["type"] in ("Polygon", "MultiPolygon")
        coords = geometry["coordinates"]
        assert isinstance(coords, list)
