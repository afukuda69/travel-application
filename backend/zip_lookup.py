from dataclasses import dataclass

import httpx

import config

GEOAPIFY_URL = "https://api.geoapify.com/v1/geocode/search"
REQUEST_TIMEOUT_SECONDS = 5.0


class GeoapifyNotConfiguredError(Exception):
    """Raised when GEOAPIFY_API_KEY is absent, empty, or whitespace-only."""


class ZipNotResolvedError(Exception):
    """Raised when Geoapify responded successfully, but no candidate result
    matched the requested U.S. postcode with valid coordinates."""


class GeoapifyRequestError(Exception):
    """Raised when the request to Geoapify itself failed: a network error,
    a timeout, a non-2xx response, or a response body that couldn't be
    parsed. Distinct from ZipNotResolvedError, which means Geoapify was
    reachable but had no matching data."""


@dataclass
class ZipLocation:
    postcode: str
    country_code: str
    latitude: float
    longitude: float
    locality: str | None = None


def lookup_zip(postcode: str) -> ZipLocation:
    """
    Look up a U.S. postcode via Geoapify forward geocoding.

    Contract:
    - Input: a U.S. postcode string, e.g. "16802".
    - Success: returns a ZipLocation (postcode, country_code, latitude,
      longitude, locality-or-None) built from the first candidate result
      whose postcode matches the input exactly, whose country_code is
      "us", and which has numeric latitude and longitude.
    - Raises GeoapifyNotConfiguredError if no API key is available (checked
      via config.get_geoapify_api_key() before any request is made).
    - Raises ZipNotResolvedError if Geoapify responds successfully but no
      candidate satisfies the match criteria above ("unresolved ZIP").
    - Raises GeoapifyRequestError if the HTTP call itself fails: network
      error, timeout, non-2xx status, or unparseable response body
      ("provider request failed"). This is deliberately distinct from
      ZipNotResolvedError.
    - Never includes the API key, the full request URL, or a raw
      provider exception in any return value or raised exception message.
    """
    api_key = config.get_geoapify_api_key()
    if api_key is None:
        raise GeoapifyNotConfiguredError("GEOAPIFY_API_KEY is not configured")

    params = {
        "postcode": postcode,
        "type": "postcode",
        "filter": "countrycode:us",
        "format": "json",
        "apiKey": api_key,
    }

    try:
        response = httpx.get(GEOAPIFY_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError:
        raise GeoapifyRequestError("Geoapify request failed") from None
    except ValueError:
        raise GeoapifyRequestError("Geoapify returned an unparseable response") from None

    for result in data.get("results", []):
        result_postcode = str(result.get("postcode", "")).strip()
        result_country = str(result.get("country_code", "")).strip().lower()
        lat = result.get("lat")
        lon = result.get("lon")
        if (
            result_postcode == postcode
            and result_country == "us"
            and isinstance(lat, (int, float))
            and isinstance(lon, (int, float))
        ):
            return ZipLocation(
                postcode=result_postcode,
                country_code=result_country,
                latitude=float(lat),
                longitude=float(lon),
                locality=result.get("city") or None,
            )

    raise ZipNotResolvedError(f"No matching U.S. postcode result for {postcode}")
