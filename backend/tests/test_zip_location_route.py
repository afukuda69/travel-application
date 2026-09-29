import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import main
import zip_lookup


class ZipLocationRouteTests(unittest.TestCase):
    """Tests for GET /api/zip-location?zip=. The controller
    (zip_lookup.lookup_zip) is mocked in every case, so no live Geoapify
    request is made."""

    def test_valid_zip_returns_location(self):
        fake_location = zip_lookup.ZipLocation(
            postcode="16802",
            country_code="us",
            latitude=40.8,
            longitude=-77.86,
            locality="State College",
        )
        with patch("zip_lookup.lookup_zip", return_value=fake_location) as mock_lookup:
            with TestClient(main.app) as client:
                response = client.get("/api/zip-location", params={"zip": "16802"})

        mock_lookup.assert_called_once_with("16802")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["postcode"], "16802")

    def test_leading_zero_zip_preserved_and_passed_through(self):
        fake_location = zip_lookup.ZipLocation(
            postcode="02134",
            country_code="us",
            latitude=42.35,
            longitude=-71.13,
            locality="Boston",
        )
        with patch("zip_lookup.lookup_zip", return_value=fake_location) as mock_lookup:
            with TestClient(main.app) as client:
                response = client.get("/api/zip-location", params={"zip": "02134"})

        # The leading zero must survive the whole request cycle: the query
        # string, FastAPI's `str` param, and what's passed to the controller.
        mock_lookup.assert_called_once_with("02134")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["postcode"], "02134")

    def test_invalid_formats_return_422_without_calling_controller(self):
        invalid_inputs = {
            "four_digits": "1234",
            "six_digits": "123456",
            "letters": "abcde",
            "empty": "",
            "spaces_only": "     ",
            "digits_with_space": "123 45",
            "digits_with_leading_space": " 1234",
        }
        for label, value in invalid_inputs.items():
            with self.subTest(label=label, value=value):
                with patch("zip_lookup.lookup_zip") as mock_lookup:
                    with TestClient(main.app) as client:
                        response = client.get("/api/zip-location", params={"zip": value})

                self.assertEqual(response.status_code, 422, f"{label!r} should be rejected")
                mock_lookup.assert_not_called()

    def test_missing_zip_param_returns_422_without_calling_controller(self):
        with patch("zip_lookup.lookup_zip") as mock_lookup:
            with TestClient(main.app) as client:
                response = client.get("/api/zip-location")

        self.assertEqual(response.status_code, 422)
        mock_lookup.assert_not_called()

    def test_unresolved_zip_returns_404(self):
        with patch("zip_lookup.lookup_zip", side_effect=zip_lookup.ZipNotResolvedError()):
            with TestClient(main.app) as client:
                response = client.get("/api/zip-location", params={"zip": "00000"})
        self.assertEqual(response.status_code, 404)

    def test_provider_failure_returns_502(self):
        with patch("zip_lookup.lookup_zip", side_effect=zip_lookup.GeoapifyRequestError()):
            with TestClient(main.app) as client:
                response = client.get("/api/zip-location", params={"zip": "16802"})
        self.assertEqual(response.status_code, 502)

    def test_missing_config_returns_503(self):
        with patch("zip_lookup.lookup_zip", side_effect=zip_lookup.GeoapifyNotConfiguredError()):
            with TestClient(main.app) as client:
                response = client.get("/api/zip-location", params={"zip": "16802"})
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
