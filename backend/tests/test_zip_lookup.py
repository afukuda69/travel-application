import unittest
from unittest.mock import patch

import httpx

import zip_lookup


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


class ZipLookupTests(unittest.TestCase):
    """Labeled mocked-response tests for zip_lookup.lookup_zip. No real
    network requests are made; httpx.get and the config helper are patched."""

    @patch("zip_lookup.config.get_geoapify_api_key", return_value="test-key")
    @patch("zip_lookup.httpx.get")
    def test_success_matching_postcode_with_coordinates(self, mock_get, _mock_key):
        """SUCCESS: a candidate matches the requested postcode, is in the
        US, and has valid coordinates -> a populated ZipLocation."""
        mock_get.return_value = FakeResponse(
            {
                "results": [
                    {
                        "postcode": "16802",
                        "country_code": "us",
                        "city": "State College",
                        "lat": 40.8,
                        "lon": -77.86,
                    }
                ]
            }
        )

        location = zip_lookup.lookup_zip("16802")

        self.assertEqual(location.postcode, "16802")
        self.assertEqual(location.country_code, "us")
        self.assertEqual(location.locality, "State College")
        self.assertAlmostEqual(location.latitude, 40.8)
        self.assertAlmostEqual(location.longitude, -77.86)

    @patch("zip_lookup.config.get_geoapify_api_key", return_value="test-key")
    @patch("zip_lookup.httpx.get")
    def test_mismatched_location_raises_unresolved(self, mock_get, _mock_key):
        """MISMATCHED LOCATION: Geoapify responds successfully, but the
        only candidate's postcode doesn't match the requested one ->
        ZipNotResolvedError ("unresolved ZIP"), not an exception from the
        HTTP layer."""
        mock_get.return_value = FakeResponse(
            {
                "results": [
                    {
                        "postcode": "90210",
                        "country_code": "us",
                        "city": "Beverly Hills",
                        "lat": 34.09,
                        "lon": -118.41,
                    }
                ]
            }
        )

        with self.assertRaises(zip_lookup.ZipNotResolvedError):
            zip_lookup.lookup_zip("16802")

    @patch("zip_lookup.config.get_geoapify_api_key", return_value="test-key")
    @patch("zip_lookup.httpx.get")
    def test_provider_failure_raises_request_error(self, mock_get, _mock_key):
        """PROVIDER FAILURE: the HTTP call itself fails (network error) ->
        GeoapifyRequestError, distinct from an unresolved ZIP."""
        mock_get.side_effect = httpx.ConnectError("mocked connection failure")

        with self.assertRaises(zip_lookup.GeoapifyRequestError):
            zip_lookup.lookup_zip("16802")

    @patch("zip_lookup.config.get_geoapify_api_key", return_value=None)
    def test_missing_config_raises_not_configured(self, _mock_key):
        """NOT CONFIGURED: no API key available -> fails fast with
        GeoapifyNotConfiguredError before any request is attempted."""
        with self.assertRaises(zip_lookup.GeoapifyNotConfiguredError):
            zip_lookup.lookup_zip("16802")


if __name__ == "__main__":
    unittest.main()
