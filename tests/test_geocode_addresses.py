"""
SEED Platform (TM), Copyright (c) Alliance for Sustainable Energy, LLC, and other contributors.
See also https://github.com/SEED-platform/building-data-utilities/blob/main/LICENSE.md
"""

import os
from unittest.mock import Mock, patch

import pytest

from building_data_utilities.common import Location
from building_data_utilities.geocode_addresses import AmazonAPIKeyError, _process_result, geocode_addresses


class TestGeocodeAddresses:
    """Simple tests for geocoding functionality"""

    def test_process_result_single_valid_location(self):
        """Test processing a valid single geocoding result"""
        # Mock a valid Amazon response
        mock_result = {
            "ResultItems": [
                {
                    "PlaceId": "AQA1",
                    "PlaceType": "PointAddress",
                    "Title": "123 Main St, Central City, CO 80427-5069, United States",
                    "Address": {
                        "Label": "123 Main St, Central City, CO 80427-5069, United States",
                        "Country": {"Code2": "US", "Code3": "USA", "Name": "United States"},
                        "Region": {"Code": "CO", "Name": "Colorado"},
                        "Locality": "Central City",
                        "PostalCode": "80427-5069",
                        "Street": "Main St",
                        "AddressNumber": "123",
                    },
                    "Position": [-105.51284, 39.80013],
                    "MapView": [-105.51401, 39.79923, -105.51167, 39.80103],
                    "MatchScores": {
                        "Overall": 1,
                        "Components": {"Address": {"Region": 1, "Locality": 1, "Intersection": [1], "AddressNumber": 1}},
                    },
                }
            ]
        }

        result = _process_result(mock_result)

        # Check basic structure
        assert "quality" in result
        assert "latitude" in result
        assert "longitude" in result
        assert "address" in result

        # Check values
        assert result["quality"] > 0.9
        assert result["latitude"] == 39.80013
        assert result["longitude"] == -105.51284
        assert result["address"] == "123 Main St"
        assert result["postal_code"] == "80427"

        # Check admin areas were flattened
        assert result["country"] == "US"
        assert result["city"] == "Central City"
        assert result["state"] == "CO"

    def test_process_result_multiple_locations(self):
        """Test processing result with multiple locations (ambiguous)"""
        mock_result = {
            "ResultItems": [
                {
                    "PlaceId": "A1",
                    "PlaceType": "PostalCode",
                    "Address": {"Label": "Golden, CO, United States"},
                    "Position": [-105.22495, 39.75665],
                    "MatchScores": {"Overall": 1, "Components": {"Address": {"PostalCode": 1}}},
                },
                {
                    "PlaceId": "A2",
                    "PlaceType": "PostalCode",
                    "Address": {"Label": "Another Place, Somewhere Else"},
                    "Position": [-100.22495, 35.75665],
                    "MatchScores": {"Overall": 1, "Components": {"Address": {"PostalCode": 1}}},
                },
            ]
        }

        result = _process_result(mock_result)
        assert result["quality"] == "Ambiguous"

    def test_process_result_low_quality(self):
        """Test processing result with low quality geocoding"""
        mock_result = {
            "ResultItems": [
                {
                    "PlaceId": "abc",
                    "Address": {"Label": "Main St Central City, CO 80427-5069, United States"},
                    "Position": [105, 39],
                    "MatchScores": {"Overall": 0.76},
                }
            ]
        }

        result = _process_result(mock_result)
        # Should return quality but not accept the location
        assert result["quality"] == "Less Than 0.90 Confidence"
        assert "latitude" not in result
        assert "longitude" not in result

    def test_process_result_no_results(self):
        """Test _process_result returns correct value when no results are found (line 40)."""
        mock_result = {"ResultItems": []}
        result = _process_result(mock_result)
        assert result["quality"] == "Ambiguous"

    def test_process_result_unexpected_branch(self):
        """Test _process_result returns 'Less Than 0.90 Confidence' for unexpected branch (line 67)."""
        # This will hit the final else branch if MatchScores is missing or low
        mock_result = {"ResultItems": [{"MatchScores": {}, "Position": [0, 0], "Address": {}}]}
        result = _process_result(mock_result)
        assert result["quality"] == "Less Than 0.90 Confidence"

    @patch("building_data_utilities.geocode_addresses.requests.post")
    def test_geocode_addresses_success(self, mock_post):
        """Test successful geocoding of addresses"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ResultItems": [
                {
                    "PlaceId": "AQAAAGAAUGu_KXBMbixCf-d95lK2i-YwdSMUkHzvPuA8U9r0RT-hwjzwLznQSmiXmhVi72LHKI3rr4UdK1yMow6d_tKvpPPVBlZcuvBCshOvG0w11Yv_7Nt7kkuVCxvtK46vp6Fkgm1_EPLZVuc0S05eMDkpOo7UIfyUQbgPSmWaxJhUg44",
                    "PlaceType": "PointAddress",
                    "Title": "123 Main St, Central City, CO 80427-5069, United States",
                    "Address": {
                        "Label": "123 Main St, Central City, CO 80427-5069, United States",
                        "Country": {"Code2": "US", "Code3": "USA", "Name": "United States"},
                        "Region": {"Code": "CO", "Name": "Colorado"},
                        "SubRegion": {"Name": "Gilpin"},
                        "Locality": "Central City",
                        "PostalCode": "80427-5069",
                        "Street": "Main St",
                        "StreetComponents": [
                            {"BaseName": "Main", "Type": "St", "TypePlacement": "AfterBaseName", "TypeSeparator": " ", "Language": "en"}
                        ],
                        "AddressNumber": "123",
                    },
                    "Position": [-105.51284, 39.80013],
                    "MapView": [-105.51401, 39.79923, -105.51167, 39.80103],
                    "MatchScores": {
                        "Overall": 1,
                        "Components": {"Address": {"Region": 1, "Locality": 1, "Intersection": [1], "AddressNumber": 1}},
                    },
                    "ParsedQuery": {
                        "Address": {
                            "Region": [{"StartIndex": 27, "EndIndex": 29, "Value": "CO", "QueryComponent": "Query"}],
                            "Locality": [{"StartIndex": 13, "EndIndex": 25, "Value": "Central City", "QueryComponent": "Query"}],
                            "Street": [{"StartIndex": 4, "EndIndex": 11, "Value": "main st", "QueryComponent": "Query"}],
                            "AddressNumber": [{"StartIndex": 0, "EndIndex": 3, "Value": "123", "QueryComponent": "Query"}],
                        }
                    },
                }
            ]
        }
        mock_post.return_value = mock_response

        # Test data
        locations = [Location(street="123 Main St", city="Central City", state="CO")]

        # Geocode
        results = geocode_addresses(locations, "fake_amazon_api_key", "fake_amazon_base_url")

        # Check results
        assert len(results) == 1
        assert results[0]["latitude"] == 39.80013
        assert results[0]["longitude"] == -105.51284
        assert str(results[0]["quality"]) == "1"

        # Verify API was called correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "geocode" in call_args[0][0]
        assert "fake_amazon_api_key" in call_args[0][0]

    @patch("building_data_utilities.geocode_addresses.requests.post")
    def test_geocode_addresses_invalid_api_key_401(self, mock_post):
        """Test handling of invalid API key (401 error)"""
        import pytest

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.content = b"Invalid API key"
        mock_post.return_value = mock_response

        locations = [Location(street="123 Main St", city="Denver", state="CO")]

        with pytest.raises(AmazonAPIKeyError, match="API Key is invalid"):
            geocode_addresses(locations, "invalid_key", "fake_amazon_base_url")

    @patch("building_data_utilities.geocode_addresses.requests.post")
    def test_geocode_addresses_api_limit_403(self, mock_post):
        """Test handling of API limit exceeded (403 error)"""
        import pytest

        mock_response = Mock()
        mock_response.status_code = 403
        mock_post.return_value = mock_response

        locations = [Location(street="123 Main St", city="Denver", state="CO")]

        with pytest.raises(AmazonAPIKeyError, match="at its limit"):
            geocode_addresses(locations, "limited_key", "fake_amazon_base_url")

    @patch("building_data_utilities.geocode_addresses.requests.post")
    def test_geocode_addresses_chunking(self, mock_post):
        """Test that large lists are properly chunked"""

        # Mock response for each chunk - each response contains results for
        # ALL locations in that chunk
        def mock_response_generator(*args, **kwargs):
            # Get the locations from the request
            locations_in_request = kwargs.get("json", {}).get("locations", [])
            results = []
            for _ in locations_in_request:
                results.append(
                    {
                        "locations": [
                            {"geocodeQualityCode": "P1AAA", "displayLatLng": {"lng": -104.9903, "lat": 39.7392}, "street": "123 Main St"}
                        ]
                    }
                )

            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"results": results}
            return mock_response

        mock_post.side_effect = mock_response_generator

        # Create more than 10 locations to test chunking
        locations = []
        for i in range(10):
            locations.append(Location(street=f"{i} Test St", city="Denver", state="CO"))

        results = geocode_addresses(locations, "test_key", "test_amazon_base_url")

        # Should have results for all locations
        assert len(results) == 10

        # Should have made multiple API calls due to chunking
        assert mock_post.call_count == 10  # 1 call/chunk per location

    def test_geocode_addresses_empty_list(self):
        """Test geocoding with empty location list"""
        results = geocode_addresses([], "test_key", "test_amazon_base_url")
        assert results == []

    @patch("building_data_utilities.geocode_addresses.requests.post")
    def test_geocode_addresses_mixed_quality_results(self, mock_post):
        """Test geocoding with mixed quality results"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            # Good quality result
            "ResultItems": [
                {
                    "PlaceId": "AQA1",
                    "PlaceType": "PointAddress",
                    "Title": "123 Main St, Central City, CO 80427-5069, United States",
                    "Address": {
                        "Label": "123 Main St, Central City, CO 80427-5069, United States",
                        "Country": {"Code2": "US", "Code3": "USA", "Name": "United States"},
                        "Locality": "Central City",
                        "PostalCode": "80427-5069",
                        "Street": "Main St",
                        "AddressNumber": "123",
                    },
                    "Position": [-105.51284, 39.80013],
                    "MapView": [-105.51401, 39.79923, -105.51167, 39.80103],
                    "MatchScores": {
                        "Overall": 1,
                        "Components": {"Address": {"Region": 1, "Locality": 1, "Intersection": [1], "AddressNumber": 1}},
                    },
                }
            ]
        }
        mock_post.return_value = mock_response

        locations = [
            Location(street="123 Main St", city="Central City", state="CO"),
        ]

        results = geocode_addresses(locations, "test_key", "test_amazon_base_url")
        assert len(results) == 1
        # First result should have coordinates
        assert "latitude" in results[0]
        assert "longitude" in results[0]

        # 2nd response
        mock_response.json.return_value = {
            # Poor quality result (matchscore < 0.9)
            "ResultItems": [
                {
                    "PlaceId": "AQA2",
                    "PlaceType": "District",
                    "Title": "Mountain View, Baldwin Park, CA, United States",
                    "Address": {"Label": "Mountain View, Baldwin Park, CA, United States"},
                    "Position": [-118.02067, 34.05324],
                    "MatchScores": {"Overall": 0.41, "Components": {"Address": {"Region": 1, "District": 0.75}}},
                }
            ]
        }
        mock_post.return_value = mock_response

        locations = [
            Location(street="1600 Amfthtr Pkway", city="Muntin Vew", state="CA"),
        ]
        results = geocode_addresses(locations, "test_key", "test_amazon_base_url")
        assert len(results) == 1
        # Second result should not have lat/lng (poor quality)
        assert "latitude" not in results[0]

        # 3rd response
        mock_response.json.return_value = {
            "ResultItems": [
                {
                    "PlaceId": "AQA3",
                    "PlaceType": "PointAddress",
                    "Title": "123 Main St, San Francisco, CA 94105-1804, United States",
                    "Address": {"Label": "123 Main St, San Francisco, CA 94105-1804, United States", "AddressNumber": "123"},
                    "Position": [-122.39417, 37.79165],
                    "MatchScores": {"Overall": 1, "Components": {"Address": {"Country": 1, "Intersection": [1], "AddressNumber": 1}}},
                },
                {
                    "PlaceId": "AQA4",
                    "PlaceType": "PointAddress",
                    "Title": "123 Main St, White Plains, NY 10601-3104, United States",
                    "Address": {"Label": "123 Main St, White Plains, NY 10601-3104, United States", "AddressNumber": "123"},
                    "Position": [-73.76911, 41.03286],
                    "MatchScores": {"Overall": 1, "Components": {"Address": {"Country": 1, "Intersection": [1], "AddressNumber": 1}}},
                },
            ]
        }
        mock_post.return_value = mock_response
        locations = [
            Location(street="123 Main St", city="", state=""),
        ]
        results = geocode_addresses(locations, "test_key", "test_amazon_base_url")
        assert len(results) == 1
        # Third result should be ambiguous
        assert results[0]["quality"] == "Ambiguous"

    @patch("building_data_utilities.geocode_addresses.requests.post")
    def test_geocode_addresses_exception_handling(self, mock_post):
        """Test geocode_addresses error handling for non-403 exception (line 67)."""
        mock_post.return_value.status_code = 500
        mock_post.return_value.json.side_effect = Exception("fail json parse")
        locations = [Location(street="fail", city="fail", state="fail")]
        with pytest.raises(Exception):  # noqa: PT011
            geocode_addresses(locations, "bad_key", "bad_url")


class TestGeocodeAddressesIntegration:
    """Integration tests for geocoding addresses - requires real API key and base URL set in env vars"""

    def setup_method(self):
        self.api_key = os.environ.get("AMAZON_API_KEY")
        self.base_url = os.environ.get("AMAZON_BASE_URL")
        self.app_id = os.environ.get("AMAZON_APP_ID")

    def test_geocode_addresses_real_amazon_api(self):
        """Integration test: actually calls the Amazon geocoding API (requires valid API key and base URL)"""
        if not self.api_key or not self.base_url or not self.app_id:
            # Skip (rather than fail) since these secrets aren't available in CI runs triggered by
            # Dependabot or forks (GitHub withholds repo secrets from those workflow runs).
            pytest.skip("AMAZON_API_KEY and AMAZON_BASE_URL and AMAZON_APP_ID environment variables not set")

        # Casa Bonita, Lakewood, Colorado
        locations = [Location(street="6715 W Colfax Ave", city="Lakewood", state="")]
        results = geocode_addresses(locations, self.api_key, self.base_url, self.app_id)
        assert len(results) == 1
        result = results[0]
        assert "latitude" in result
        assert "longitude" in result
        assert result["quality"] == 1 or result["quality"] > 0.9
        # Check that the address/city/state in the result match Casa Bonita
        assert "colfax" in result["address"].lower()
        assert result.get("city", "").lower() == "lakewood"
        assert result.get("state", "").upper() == "CO"

        # check the lat long +/- degrees
        assert 39.73 < result["latitude"] < 39.75
        assert -105.09 < result["longitude"] < -105.07
