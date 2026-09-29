from dataclasses import dataclass

import httpx

import config

GEOAPIFY_PLACES_URL = "https://api.geoapify.com/v2/places"
REQUEST_TIMEOUT_SECONDS = 5.0
SEARCH_RADIUS_METERS = 5000
RESULT_LIMIT = 20


class GeoapifyNotConfiguredError(Exception):
    """Raised when GEOAPIFY_API_KEY is absent, empty, or whitespace-only."""


class PlacesRateLimitedError(Exception):
    """Raised when Geoapify responds with 429 (rate limit or quota exceeded)."""


class PlacesRequestError(Exception):
    """Raised when the request to Geoapify itself failed: a network error,
    a timeout, a non-2xx (non-429) status, or a response body that couldn't
    be parsed."""


@dataclass
class NearbyHotel:
    place_id: str
    name: str | None
    address: str | None
    latitude: float
    longitude: float
    distance_m: float | None = None


def find_nearby_hotels(latitude: float, longitude: float) -> list[NearbyHotel]:
    """
    Find hotels near a point via the Geoapify Places API.

    Contract:
    - Input: latitude/longitude of an already-resolved point (e.g. from
      zip_lookup.lookup_zip). This function does no geocoding of its own
      and never chooses a fallback location.
    - Success: returns a list of NearbyHotel — possibly empty. An empty
      list means "Geoapify responded successfully with zero matching
      places," which is NOT a failure; callers must not conflate the two.
    - Any result missing valid numeric coordinates is skipped. Missing
      name/address are kept as None rather than invented. No price,
      rating, or availability fields exist on NearbyHotel.
    - Raises GeoapifyNotConfiguredError if no API key is available
      (checked before any request is made).
    - Raises PlacesRateLimitedError if Geoapify responds with 429.
    - Raises PlacesRequestError for any other failure: network error,
      timeout, other non-2xx status, or an unparseable response body.
    - Never includes the API key, the full request URL, or a raw provider
      exception in any return value or raised exception message.
    """
    api_key = config.get_geoapify_api_key()
    if api_key is None:
        raise GeoapifyNotConfiguredError("GEOAPIFY_API_KEY is not configured")

    params = {
        "categories": "accommodation.hotel",
        "filter": f"circle:{longitude},{latitude},{SEARCH_RADIUS_METERS}",
        "bias": f"proximity:{longitude},{latitude}",
        "limit": RESULT_LIMIT,
        "apiKey": api_key,
    }

    try:
        response = httpx.get(GEOAPIFY_PLACES_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    except httpx.HTTPError:
        raise PlacesRequestError("Geoapify Places request failed") from None

    if response.status_code == 429:
        raise PlacesRateLimitedError("Geoapify rate limit or quota exceeded")

    try:
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError:
        raise PlacesRequestError("Geoapify Places request failed") from None
    except ValueError:
        raise PlacesRequestError("Geoapify returned an unparseable response") from None

    hotels = []
    for feature in data.get("features", []):
        properties = feature.get("properties", {}) or {}
        geometry = feature.get("geometry", {}) or {}
        coordinates = geometry.get("coordinates")

        lat = None
        lon = None
        if isinstance(coordinates, list) and len(coordinates) == 2:
            lon, lat = coordinates[0], coordinates[1]
        if not isinstance(lat, (int, float)):
            lat = properties.get("lat")
        if not isinstance(lon, (int, float)):
            lon = properties.get("lon")

        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue

        place_id = properties.get("place_id")
        if not place_id:
            continue

        distance = properties.get("distance")

        hotels.append(
            NearbyHotel(
                place_id=str(place_id),
                name=properties.get("name") or None,
                address=properties.get("formatted") or None,
                latitude=float(lat),
                longitude=float(lon),
                distance_m=float(distance) if isinstance(distance, (int, float)) else None,
            )
        )

    return hotels
