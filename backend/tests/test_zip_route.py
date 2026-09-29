import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import main
import zip_lookup


class ZipRouteTests(unittest.TestCase):
    """Route-level tests for GET /api/demo/zip-location. The controller
    (zip_lookup.lookup_zip) is mocked in every case, so no live Geoapify
    request is made."""

    def test_success_returns_zip_location(self):
        fake_location = zip_lookup.ZipLocation(
            postcode="16802",
            country_code="us",
            latitude=40.8,
            longitude=-77.86,
            locality="State College",
        )
        with patch("zip_lookup.lookup_zip", return_value=fake_location) as mock_lookup:
            with TestClient(main.app) as client:
                response = client.get("/api/demo/zip-location")

        mock_lookup.assert_called_once_with(main.DEMO_ZIP_POSTCODE)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "postcode": "16802",
                "country_code": "us",
                "latitude": 40.8,
                "longitude": -77.86,
                "locality": "State College",
            },
        )

    def test_missing_config_returns_503(self):
        with patch("zip_lookup.lookup_zip", side_effect=zip_lookup.GeoapifyNotConfiguredError()):
            with TestClient(main.app) as client:
                response = client.get("/api/demo/zip-location")
        self.assertEqual(response.status_code, 503)

    def test_unresolved_zip_returns_404(self):
        with patch("zip_lookup.lookup_zip", side_effect=zip_lookup.ZipNotResolvedError()):
            with TestClient(main.app) as client:
                response = client.get("/api/demo/zip-location")
        self.assertEqual(response.status_code, 404)

    def test_provider_failure_returns_502(self):
        with patch("zip_lookup.lookup_zip", side_effect=zip_lookup.GeoapifyRequestError()):
            with TestClient(main.app) as client:
                response = client.get("/api/demo/zip-location")
        self.assertEqual(response.status_code, 502)


if __name__ == "__main__":
    unittest.main()
