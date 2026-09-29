import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import main
import places_lookup
import zip_lookup


FAKE_LOCATION = zip_lookup.ZipLocation(
    postcode="16802",
    country_code="us",
    latitude=40.8,
    longitude=-77.86,
    locality="State College",
)


class HotelsNearbyRouteTests(unittest.TestCase):
    """Tests for GET /api/hotels/nearby?zip=. zip_lookup.lookup_zip and
    places_lookup.find_nearby_hotels are both mocked, so no live requests
    are made."""

    def test_hotels_found_returns_location_and_hotels(self):
        fake_hotels = [
            places_lookup.NearbyHotel(
                place_id="p1", name="Hotel A", address="123 Main St",
                latitude=40.81, longitude=-77.85, distance_m=150.0,
            )
        ]
        with patch("zip_lookup.lookup_zip", return_value=FAKE_LOCATION), \
             patch("places_lookup.find_nearby_hotels", return_value=fake_hotels) as mock_places:
            with TestClient(main.app) as client:
                response = client.get("/api/hotels/nearby", params={"zip": "16802"})

        mock_places.assert_called_once_with(40.8, -77.86)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["location"]["postcode"], "16802")
        self.assertEqual(body["radius_m"], places_lookup.SEARCH_RADIUS_METERS)
        self.assertEqual(len(body["hotels"]), 1)
        self.assertEqual(body["hotels"][0]["place_id"], "p1")

    def test_empty_hotel_results_is_200_not_error(self):
        with patch("zip_lookup.lookup_zip", return_value=FAKE_LOCATION), \
             patch("places_lookup.find_nearby_hotels", return_value=[]):
            with TestClient(main.app) as client:
                response = client.get("/api/hotels/nearby", params={"zip": "16802"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["hotels"], [])

    def test_invalid_zip_returns_422_without_calling_lookup_or_places(self):
        with patch("zip_lookup.lookup_zip") as mock_lookup, \
             patch("places_lookup.find_nearby_hotels") as mock_places:
            with TestClient(main.app) as client:
                response = client.get("/api/hotels/nearby", params={"zip": "1234"})

        self.assertEqual(response.status_code, 422)
        mock_lookup.assert_not_called()
        mock_places.assert_not_called()

    def test_unresolved_zip_returns_404_and_never_calls_places(self):
        with patch("zip_lookup.lookup_zip", side_effect=zip_lookup.ZipNotResolvedError()), \
             patch("places_lookup.find_nearby_hotels") as mock_places:
            with TestClient(main.app) as client:
                response = client.get("/api/hotels/nearby", params={"zip": "00000"})

        self.assertEqual(response.status_code, 404)
        mock_places.assert_not_called()

    def test_zip_provider_failure_returns_502(self):
        with patch("zip_lookup.lookup_zip", side_effect=zip_lookup.GeoapifyRequestError()), \
             patch("places_lookup.find_nearby_hotels") as mock_places:
            with TestClient(main.app) as client:
                response = client.get("/api/hotels/nearby", params={"zip": "16802"})

        self.assertEqual(response.status_code, 502)
        mock_places.assert_not_called()

    def test_places_provider_failure_returns_502(self):
        with patch("zip_lookup.lookup_zip", return_value=FAKE_LOCATION), \
             patch("places_lookup.find_nearby_hotels", side_effect=places_lookup.PlacesRequestError()):
            with TestClient(main.app) as client:
                response = client.get("/api/hotels/nearby", params={"zip": "16802"})

        self.assertEqual(response.status_code, 502)

    def test_places_rate_limited_returns_429(self):
        with patch("zip_lookup.lookup_zip", return_value=FAKE_LOCATION), \
             patch("places_lookup.find_nearby_hotels", side_effect=places_lookup.PlacesRateLimitedError()):
            with TestClient(main.app) as client:
                response = client.get("/api/hotels/nearby", params={"zip": "16802"})

        self.assertEqual(response.status_code, 429)

    def test_not_configured_returns_503(self):
        with patch("zip_lookup.lookup_zip", side_effect=zip_lookup.GeoapifyNotConfiguredError()), \
             patch("places_lookup.find_nearby_hotels") as mock_places:
            with TestClient(main.app) as client:
                response = client.get("/api/hotels/nearby", params={"zip": "16802"})

        self.assertEqual(response.status_code, 503)
        mock_places.assert_not_called()


if __name__ == "__main__":
    unittest.main()
