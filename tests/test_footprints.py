"""
SEED Platform (TM), Copyright (c) Alliance for Sustainable Energy, LLC, and other contributors.
See also https://github.com/SEED-platform/building-data-utilities/blob/main/LICENSE.md
"""

import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import MultiPolygon, Point, Polygon

from building_data_utilities import footprints


class TestFootprints(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.quadkeys_dir = Path("quadkeys")

        # Create a simple test polygon (roughly a square)
        self.test_polygon = Polygon([(-104.99, 39.73), (-104.98, 39.73), (-104.98, 39.74), (-104.99, 39.74), (-104.99, 39.73)])

        # Create sample MS footprint data
        self.sample_ms_data = {
            "geometry": [Polygon([(-104.985, 39.735), (-104.984, 39.735), (-104.984, 39.736), (-104.985, 39.736), (-104.985, 39.735)])],
            "height": [15.5],
            "id": [1],
        }
        self.sample_ms_gdf = gpd.GeoDataFrame(self.sample_ms_data, crs="EPSG:4326")

        # Create sample OSM footprint data with multi-index
        index = pd.MultiIndex.from_tuples([("way", 12345)], names=["element", "id"])
        self.sample_osm_data = {
            "geometry": [Polygon([(-104.985, 39.735), (-104.984, 39.735), (-104.984, 39.736), (-104.985, 39.736), (-104.985, 39.735)])],
            "building": ["yes"],
            "addr:city": ["Denver"],
            "addr:street": ["Main St"],
            "addr:housenumber": ["123"],
        }
        self.sample_osm_gdf = gpd.GeoDataFrame(self.sample_osm_data, index=index, crs="EPSG:4326")

    @patch("building_data_utilities.footprints.mercantile")
    @patch("building_data_utilities.footprints.gpd.GeoDataFrame")
    def test_get_quadkeys_for_polygon(self, mock_gdf_class, mock_mercantile):
        """Test quadkey generation for a polygon."""
        # Mock the GeoDataFrame creation and bounds
        mock_gdf = Mock()
        mock_gdf.bounds.iloc = [pd.Series({"minx": -104.99, "miny": 39.73, "maxx": -104.98, "maxy": 39.74})]
        mock_gdf_class.return_value = mock_gdf

        # Mock mercantile functions
        mock_tile = Mock()
        mock_mercantile.tiles.return_value = [mock_tile]
        mock_mercantile.quadkey.return_value = "023010203"

        result = footprints.get_quadkeys_for_polygon(self.test_polygon)

        self.assertEqual(result, [23010203])
        mock_mercantile.tiles.assert_called_once()
        mock_mercantile.quadkey.assert_called_once_with(mock_tile)

    @patch("builtins.open")
    @patch("building_data_utilities.footprints.gzip")
    @patch("building_data_utilities.footprints.gpd")
    @patch("building_data_utilities.footprints.pd.concat")
    def test_load_ms_footprints(self, mock_concat, mock_gpd, mock_gzip, mock_open):
        """Test loading Microsoft footprints."""
        # Mock file existence
        with patch.object(Path, "exists", return_value=True):
            # Mock GeoDataFrame operations
            mock_aoi_gdf = Mock()
            mock_aoi_gdf.geometry.iloc = [self.test_polygon]

            mock_loaded_gdf = self.sample_ms_gdf.copy()

            mock_gpd.GeoDataFrame.return_value = mock_aoi_gdf
            mock_gpd.read_file.return_value = mock_loaded_gdf
            mock_concat.return_value = self.sample_ms_gdf

            # Mock gzip operations
            mock_file = Mock()
            mock_gzip.open.return_value.__enter__.return_value = mock_file

            result = footprints.load_ms_footprints(self.test_polygon, [23010203], self.quadkeys_dir)

            self.assertIsInstance(result, gpd.GeoDataFrame)
            mock_gpd.read_file.assert_called_once_with(mock_file)

    def test_load_ms_footprints_no_quadkeys(self):
        """Test loading MS footprints with no quadkeys."""
        result = footprints.load_ms_footprints(self.test_polygon, [], self.quadkeys_dir)

        self.assertIsInstance(result, gpd.GeoDataFrame)
        self.assertEqual(len(result), 0)

    @patch("building_data_utilities.footprints.encode_ubid")
    @patch("building_data_utilities.footprints.centroid")
    def test_process_ms_footprints(self, mock_centroid, mock_encode_ubid):
        """Test processing Microsoft footprints."""
        # Mock UBID functions
        mock_encode_ubid.return_value = "test_ubid"
        mock_point = Point(-104.9845, 39.7355)
        mock_centroid.return_value = mock_point

        result = footprints.process_ms_footprints(self.sample_ms_gdf.copy())

        self.assertIn("ubid", result.columns)
        self.assertIn("latitude", result.columns)
        self.assertIn("longitude", result.columns)
        self.assertIn("footprint_area_m2", result.columns)
        self.assertIn("footprint_area_ft2", result.columns)
        self.assertIn("street_address", result.columns)

        # Check that height -1 is handled
        test_gdf = self.sample_ms_gdf.copy()
        test_gdf.loc[0, "height"] = -1
        result = footprints.process_ms_footprints(test_gdf)
        self.assertIsNone(result.loc[0, "height"])

    @patch("building_data_utilities.footprints.ox.features_from_polygon")
    def test_load_osm_footprints(self, mock_ox_features):
        """Test loading OSM footprints."""
        mock_ox_features.return_value = self.sample_osm_gdf

        result = footprints.load_osm_footprints(self.test_polygon)

        self.assertIsInstance(result, gpd.GeoDataFrame)
        self.assertEqual(len(result), 1)
        mock_ox_features.assert_called_once_with(self.test_polygon, tags={"building": True})

    @patch("building_data_utilities.footprints.ox.features_from_polygon")
    def test_load_osm_footprints_empty(self, mock_ox_features):
        """Test loading OSM footprints when none are found."""
        mock_ox_features.return_value = gpd.GeoDataFrame()

        result = footprints.load_osm_footprints(self.test_polygon)

        self.assertIsInstance(result, gpd.GeoDataFrame)
        self.assertEqual(len(result), 0)

    @patch("building_data_utilities.footprints.encode_ubid")
    @patch("building_data_utilities.footprints.centroid")
    def test_process_osm_footprints(self, mock_centroid, mock_encode_ubid):
        """Test processing OSM footprints."""
        # Mock UBID functions
        mock_encode_ubid.return_value = "test_ubid"
        mock_point = Point(-104.9845, 39.7355)
        mock_centroid.return_value = mock_point

        result = footprints.process_osm_footprints(self.sample_osm_gdf.copy())

        self.assertIn("ubid", result.columns)
        self.assertIn("latitude", result.columns)
        self.assertIn("longitude", result.columns)
        self.assertIn("footprint_area_m2", result.columns)
        self.assertIn("footprint_area_ft2", result.columns)
        self.assertIn("osm_url", result.columns)
        self.assertIn("osm_id", result.columns)

        # Check that building types are processed
        self.assertEqual(result.loc[0, "building_type"], "Unknown")  # 'yes' -> 'Unknown'

    def test_process_osm_footprints_building_types(self):
        """Test OSM building type processing."""
        # Test different building types
        test_data = self.sample_osm_data.copy()
        test_data["building"] = ["residential", "yes", "roof", "commercial"]
        test_data["geometry"] = [self.sample_osm_data["geometry"][0]] * 4

        index = pd.MultiIndex.from_tuples([("way", 1), ("way", 2), ("way", 3), ("way", 4)], names=["element", "id"])

        test_gdf = gpd.GeoDataFrame(test_data, index=index, crs="EPSG:4326")

        with patch("building_data_utilities.footprints.encode_ubid"), patch("building_data_utilities.footprints.centroid"):
            result = footprints.process_osm_footprints(test_gdf)

        # Should have 3 buildings (roof is filtered out)
        self.assertEqual(len(result), 3)

        # Check building type mapping
        building_types = result["building_type"].tolist()
        self.assertIn("Unknown", building_types)  # yes -> Unknown
        self.assertIn("commercial", building_types)  # commercial stays commercial

    def test_process_osm_address_fields(self):
        """Test OSM address field processing."""
        test_gdf = self.sample_osm_gdf.copy().reset_index()

        # Add some test data with missing fields
        test_gdf.loc[0, "addr:housenumber"] = "123"
        test_gdf.loc[0, "addr:street"] = "Main St"
        test_gdf.loc[0, "addr:city"] = "Denver"
        test_gdf.loc[0, "addr:state"] = "CO"
        test_gdf.loc[0, "addr:postcode"] = "80202"

        footprints._process_osm_address_fields(test_gdf)

        self.assertEqual(test_gdf.loc[0, "street_address"], "123 Main St")
        self.assertEqual(test_gdf.loc[0, "city"], "Denver")
        self.assertEqual(test_gdf.loc[0, "state"], "CO")
        self.assertEqual(test_gdf.loc[0, "postal_code"], "80202")
        self.assertEqual(test_gdf.loc[0, "country"], "")

    def test_process_osm_address_fields_missing_data(self):
        """Test OSM address field processing with missing data."""
        # Create a minimal GeoDataFrame without address fields
        test_gdf = gpd.GeoDataFrame({"geometry": [self.test_polygon], "building": ["yes"]}).reset_index()

        footprints._process_osm_address_fields(test_gdf)

        self.assertEqual(test_gdf.loc[0, "street_address"], "")
        self.assertEqual(test_gdf.loc[0, "city"], "")
        self.assertEqual(test_gdf.loc[0, "state"], "")
        self.assertEqual(test_gdf.loc[0, "postal_code"], "")

    def test_osm_url_creation(self):
        """Test OSM URL creation with different index formats."""
        # Test with element and osm_id columns
        test_gdf = pd.DataFrame({"element": ["way"], "id": [12345], "geometry": [self.test_polygon]})

        with patch("building_data_utilities.footprints.encode_ubid"), patch("building_data_utilities.footprints.centroid"):
            test_gdf = gpd.GeoDataFrame(test_gdf)
            result = footprints.process_osm_footprints(test_gdf)

            self.assertEqual(result.loc[0, "osm_url"], "https://www.openstreetmap.org/way/12345")

    def test_build_point_query_polygon(self):
        """Test that a small padded box is built around each point (not one bbox spanning all points)."""
        points = [
            {"latitude": 39.7, "longitude": -104.9},
            {"latitude": 39.71, "longitude": -104.95},
        ]

        polygon = footprints.build_point_query_polygon(points, buffer_degrees=0.01)

        # The overall bounds should still cover both points plus padding...
        minx, miny, maxx, maxy = polygon.bounds
        self.assertAlmostEqual(minx, -104.96, places=5)
        self.assertAlmostEqual(maxx, -104.89, places=5)
        self.assertAlmostEqual(miny, 39.69, places=5)
        self.assertAlmostEqual(maxy, 39.72, places=5)

        # All input points should fall within the resulting geometry
        for point in points:
            self.assertTrue(polygon.contains(Point(point["longitude"], point["latitude"])))

        # ...but a point far from both should NOT be inside the (per-point) union, since each
        # point only contributes its own small buffered box rather than one bbox spanning both.
        self.assertFalse(polygon.contains(Point(-104.925, 39.705)))

    def test_build_point_query_polygon_far_apart_points_stay_disjoint(self):
        """Test that widely separated points don't get swept into one giant bounding box."""
        points = [
            {"latitude": 39.7355, "longitude": -104.9845},  # Denver
            {"latitude": 45.0, "longitude": -110.0},  # far away (Montana)
        ]

        polygon = footprints.build_point_query_polygon(points, buffer_degrees=0.003)

        self.assertIsInstance(polygon, MultiPolygon)
        self.assertEqual(len(polygon.geoms), 2)

        # A point roughly "between" the two selected points should NOT be covered
        self.assertFalse(polygon.contains(Point(-107.5, 42.4)))

    def test_get_quadkeys_for_multipolygon_stays_small(self):
        """Test that quadkeys for widely separated points are computed per-part, not via one huge bbox."""
        points = [
            {"latitude": 39.7355, "longitude": -104.9845},  # Denver
            {"latitude": 45.0, "longitude": -110.0},  # far away (Montana)
        ]
        polygon = footprints.build_point_query_polygon(points, buffer_degrees=0.003)

        quadkeys = footprints.get_quadkeys_for_polygon(polygon)

        # Each small per-point box should only span a small handful of z9 tiles (not the dozens
        # of tiles that a single bbox spanning Denver-to-Montana would sweep in).
        self.assertLessEqual(len(quadkeys), 4)

    def test_match_footprints_to_points_overlap_only(self):
        """Test that only footprints containing a query point are returned as matched."""
        footprint_inside = Polygon([(-104.985, 39.735), (-104.984, 39.735), (-104.984, 39.736), (-104.985, 39.736)])
        footprint_far_away = Polygon([(-105.5, 40.5), (-105.4, 40.5), (-105.4, 40.6), (-105.5, 40.6)])

        footprints_gdf = gpd.GeoDataFrame({"height": [15.5, 22.0], "geometry": [footprint_inside, footprint_far_away]}, crs="EPSG:4326")
        points_gdf = gpd.GeoDataFrame(
            {"point_id": ["row-1"]},
            geometry=[Point(-104.9845, 39.7355)],  # inside footprint_inside
            crs="EPSG:4326",
        )

        matched, unmatched = footprints.match_footprints_to_points(points_gdf, footprints_gdf)

        self.assertEqual(len(matched), 1)
        self.assertEqual(matched.iloc[0]["matched_point_id"], "row-1")
        self.assertAlmostEqual(matched.iloc[0]["height"], 15.5)

        self.assertEqual(len(unmatched), 1)
        self.assertAlmostEqual(unmatched.iloc[0]["height"], 22.0)

    def test_match_footprints_to_points_no_overlap(self):
        """Test that a point outside every footprint (and beyond the nearest-fallback threshold) results in no matches."""
        footprint = Polygon([(-104.985, 39.735), (-104.984, 39.735), (-104.984, 39.736), (-104.985, 39.736)])
        footprints_gdf = gpd.GeoDataFrame({"height": [15.5]}, geometry=[footprint], crs="EPSG:4326")
        points_gdf = gpd.GeoDataFrame({"point_id": ["row-1"]}, geometry=[Point(-104.9, 39.7)], crs="EPSG:4326")

        matched, unmatched = footprints.match_footprints_to_points(points_gdf, footprints_gdf)

        self.assertEqual(len(matched), 0)
        self.assertEqual(len(unmatched), 1)

    def test_match_footprints_to_points_falls_back_to_closest(self):
        """A point just outside a footprint (but within the nearest-fallback threshold) should still match it."""
        footprint = Polygon([(-104.985, 39.735), (-104.984, 39.735), (-104.984, 39.736), (-104.985, 39.736)])
        footprints_gdf = gpd.GeoDataFrame({"height": [15.5]}, geometry=[footprint], crs="EPSG:4326")
        # Just outside the polygon (by ~0.0005 degrees), well within the default 0.003 threshold.
        points_gdf = gpd.GeoDataFrame({"point_id": ["row-1"]}, geometry=[Point(-104.9855, 39.7355)], crs="EPSG:4326")

        matched, unmatched = footprints.match_footprints_to_points(points_gdf, footprints_gdf)

        self.assertEqual(len(matched), 1)
        self.assertEqual(matched.iloc[0]["matched_point_id"], "row-1")
        self.assertEqual(matched.iloc[0]["footprint_match"], "closest")
        self.assertAlmostEqual(matched.iloc[0]["height"], 15.5)
        self.assertEqual(len(unmatched), 0)

    def test_footprints_to_feature_dicts(self):
        """Test conversion of a footprints GeoDataFrame into plain GeoJSON Feature dicts."""
        footprint = Polygon([(-104.985, 39.735), (-104.984, 39.735), (-104.984, 39.736), (-104.985, 39.736)])
        gdf = gpd.GeoDataFrame({"height": [15.5], "matched_point_id": ["row-1"]}, geometry=[footprint], crs="EPSG:4326")

        features = footprints.footprints_to_feature_dicts(gdf)

        self.assertEqual(len(features), 1)
        self.assertEqual(features[0]["type"], "Feature")
        self.assertEqual(features[0]["properties"]["matched_point_id"], "row-1")
        self.assertAlmostEqual(features[0]["properties"]["height"], 15.5)
        self.assertEqual(features[0]["geometry"]["type"], "Polygon")

    def test_footprints_to_feature_dicts_empty(self):
        """Test that an empty GeoDataFrame produces an empty feature list."""
        empty_gdf = gpd.GeoDataFrame()

        self.assertEqual(footprints.footprints_to_feature_dicts(empty_gdf), [])

    def test_match_points_to_ms_footprints_empty_points(self):
        """Test that an empty points list returns an empty result dict without touching disk."""
        self.assertEqual(footprints.match_points_to_ms_footprints([], self.quadkeys_dir), {})

    @patch("pathlib.Path.exists")
    @patch("gzip.open")
    @patch("geopandas.read_file")
    def test_match_points_to_ms_footprints_batches_per_quadkey(self, mock_read_file, mock_gzip_open, mock_exists):
        """
        Two points that land in the same MS quadkey tile should only load/read that tile's file
        once, and be matched via a single batched spatial join rather than one join per point.
        """
        mock_exists.return_value = True
        mock_gzip_open.return_value.__enter__ = Mock(return_value=Mock())
        mock_gzip_open.return_value.__exit__ = Mock(return_value=False)

        footprint_a = Polygon([(-104.985, 39.735), (-104.984, 39.735), (-104.984, 39.736), (-104.985, 39.736)])
        footprint_b = Polygon([(-104.981, 39.735), (-104.980, 39.735), (-104.980, 39.736), (-104.981, 39.736)])
        footprints_gdf = gpd.GeoDataFrame({"height": [15.5, 20.0]}, geometry=[footprint_a, footprint_b], crs="EPSG:4326")
        mock_read_file.return_value = footprints_gdf

        points = [
            {"index": "row-1", "latitude": 39.7355, "longitude": -104.9845},  # inside footprint_a
            {"index": "row-2", "latitude": 39.7355, "longitude": -104.9805},  # inside footprint_b
        ]

        results = footprints.match_points_to_ms_footprints(points, self.quadkeys_dir)

        # Only one quadkey file should have been read, even though there are 2 points.
        self.assertEqual(mock_read_file.call_count, 1)

        self.assertEqual(set(results.keys()), {"row-1", "row-2"})
        self.assertEqual(results["row-1"]["footprint_match"], "intersection")
        self.assertAlmostEqual(results["row-1"]["height"], 15.5)
        self.assertEqual(results["row-2"]["footprint_match"], "intersection")
        self.assertAlmostEqual(results["row-2"]["height"], 20.0)

    @patch("pathlib.Path.exists")
    @patch("gzip.open")
    @patch("geopandas.read_file")
    def test_match_points_to_ms_footprints_falls_back_to_closest(self, mock_read_file, mock_gzip_open, mock_exists):
        """A point that doesn't intersect any footprint should fall back to the nearest one."""
        mock_exists.return_value = True
        mock_gzip_open.return_value.__enter__ = Mock(return_value=Mock())
        mock_gzip_open.return_value.__exit__ = Mock(return_value=False)

        footprint = Polygon([(-104.985, 39.735), (-104.984, 39.735), (-104.984, 39.736), (-104.985, 39.736)])
        footprints_gdf = gpd.GeoDataFrame({"height": [15.5]}, geometry=[footprint], crs="EPSG:4326")
        mock_read_file.return_value = footprints_gdf

        points = [{"index": "row-1", "latitude": 39.7, "longitude": -104.9}]  # not inside the footprint

        results = footprints.match_points_to_ms_footprints(points, self.quadkeys_dir)

        self.assertEqual(results["row-1"]["footprint_match"], "closest")
        self.assertAlmostEqual(results["row-1"]["height"], 15.5)

    @patch("pathlib.Path.exists")
    def test_match_points_to_ms_footprints_missing_quadkey_file(self, mock_exists):
        """Points whose quadkey tile file doesn't exist on disk should be omitted from results."""
        mock_exists.return_value = False

        points = [{"index": "row-1", "latitude": 39.7355, "longitude": -104.9845}]

        self.assertEqual(footprints.match_points_to_ms_footprints(points, self.quadkeys_dir), {})

    def test_merge_footprint_geodataframes(self):
        """Test merging two footprint GeoDataFrames with overlapping polygons and UBIDs."""
        gdf_1 = gpd.GeoDataFrame(
            {
                "ubid_1": ["A", "B"],
                "height_1": [10, 20],
                "geometry": [Polygon([(0, 0), (2, 0), (2, 2), (0, 2), (0, 0)]), Polygon([(3, 3), (5, 3), (5, 5), (3, 5), (3, 3)])],
            },
            crs="EPSG:4326",
        )

        gdf_2 = gpd.GeoDataFrame(
            {
                "ubid_2": ["A", "C"],
                "height_2": [15, 25],
                "geometry": [Polygon([(1, 1), (3, 1), (3, 3), (1, 3), (1, 1)]), Polygon([(6, 6), (8, 6), (8, 8), (6, 8), (6, 6)])],
            },
            crs="EPSG:4326",
        )

        merged = footprints.merge_footprint_geodataframes(gdf_1, gdf_2)

        assert len(merged) > 0, "Merged GeoDataFrame should not be empty"
        assert "geometry" in merged.columns, "Merged GeoDataFrame should have geometry column"
        assert "ubid" in merged.columns, "Merged GeoDataFrame should have ubid column"


if __name__ == "__main__":
    pytest.main([__file__])
