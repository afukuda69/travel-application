import unittest
from unittest.mock import patch

import httpx

import places_lookup


class FakeResponse:
    """Minimal stand-in for httpx.Response, used only in these mocked tests."""

    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if not (200 <= self.status_code < 300):
            raise httpx.HTTPError("mocked non-2xx status")

    def json(self):
        return self._json_data


def _feature(place_id="p1", name="Test Hotel", lat=40.8, lon=-77.86, distance=120, formatted="123 Main St"):
    return {
        "type": "Feature",
        "properties": {
            "place_id": place_id,
            "name": name,
            "formatted": formatted,
            "distance": distance,
        },
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
    }


class PlacesLookupTests(unittest.TestCase):
    """Labeled mocked-response tests for places_lookup.find_nearby_hotels.
    No real network requests are made."""

    @patch("places_lookup.config.get_geoapify_api_key", return_value="test-key")
    @patch("places_lookup.httpx.get")
    def test_hotels_found(self, mock_get, _mock_key):
        """HOTELS FOUND: two well-formed features -> two NearbyHotel results."""
        mock_get.return_value = FakeResponse(
            {"features": [_feature(place_id="p1", name="Hotel A"), _feature(place_id="p2", name="Hotel B")]}
        )

        hotels = places_lookup.find_nearby_hotels(40.8, -77.86)

        self.assertEqual(len(hotels), 2)
        self.assertEqual(hotels[0].place_id, "p1")
        self.assertEqual(hotels[0].name, "Hotel A")
        self.assertEqual(hotels[0].address, "123 Main St")
        self.assertEqual(hotels[0].distance_m, 120)

    @patch("places_lookup.config.get_geoapify_api_key", return_value="test-key")
    @patch("places_lookup.httpx.get")
    def test_empty_results_is_success_not_failure(self, mock_get, _mock_key):
        """EMPTY RESULTS: Geoapify responds 200 with zero features -> an
        empty list, not an exception."""
        mock_get.return_value = FakeResponse({"features": []})

        hotels = places_lookup.find_nearby_hotels(40.8, -77.86)

        self.assertEqual(hotels, [])

    @patch("places_lookup.config.get_geoapify_api_key", return_value="test-key")
    @patch("places_lookup.httpx.get")
    def test_results_missing_names_and_invalid_coords_are_handled(self, mock_get, _mock_key):
        """MISSING NAME/COORDS: a feature with no name keeps name=None; a
        feature with no coordinates is skipped entirely, not invented."""
        no_name_feature = _feature(place_id="p1", name=None)
        no_coords_feature = {
            "type": "Feature",
            "properties": {"place_id": "p2", "name": "Ghost Hotel"},
            "geometry": {"type": "Point", "coordinates": None},
        }
        mock_get.return_value = FakeResponse({"features": [no_name_feature, no_coords_feature]})

        hotels = places_lookup.find_nearby_hotels(40.8, -77.86)

        self.assertEqual(len(hotels), 1)
        self.assertEqual(hotels[0].place_id, "p1")
        self.assertIsNone(hotels[0].name)

    @patch("places_lookup.config.get_geoapify_api_key", return_value="test-key")
    @patch("places_lookup.httpx.get")
    def test_provider_failure_raises_request_error(self, mock_get, _mock_key):
        """PROVIDER FAILURE: the HTTP call itself fails (network error) ->
        PlacesRequestError, distinct from empty results."""
        mock_get.side_effect = httpx.ConnectError("mocked connection failure")

        with self.assertRaises(places_lookup.PlacesRequestError):
            places_lookup.find_nearby_hotels(40.8, -77.86)

    @patch("places_lookup.config.get_geoapify_api_key", return_value="test-key")
    @patch("places_lookup.httpx.get")
    def test_rate_limited_raises_distinct_error(self, mock_get, _mock_key):
        """429: rate limit / quota exceeded -> PlacesRateLimitedError, not
        PlacesRequestError and not an empty list."""
        mock_get.return_value = FakeResponse({}, status_code=429)

        with self.assertRaises(places_lookup.PlacesRateLimitedError):
            places_lookup.find_nearby_hotels(40.8, -77.86)

    @patch("places_lookup.config.get_geoapify_api_key", return_value=None)
    def test_missing_config_raises_not_configured(self, _mock_key):
        """NOT CONFIGURED: no API key -> fails fast, no request attempted."""
        with self.assertRaises(places_lookup.GeoapifyNotConfiguredError):
            places_lookup.find_nearby_hotels(40.8, -77.86)


if __name__ == "__main__":
    unittest.main()
