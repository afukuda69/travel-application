import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import main
import models

SAMPLE_PAYLOAD = {
    "hotel_id": "h1",
    "name": "Test Hotel",
    "address": "1 Main St",
    "latitude": 40.8,
    "longitude": -77.86,
    "zip": "16802",
    "locality": "State College",
}


class SavedHotelsRouteTests(unittest.TestCase):
    """Route-level tests for /api/saved-hotels*, run against a fresh
    temporary SQLite file per test — never the real backend/travel.db."""

    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._tmp_path = tmp.name
        self._patcher = patch.object(models, "DB_PATH", self._tmp_path)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        os.unlink(self._tmp_path)

    def test_save_list_and_delete_roundtrip(self):
        with TestClient(main.app) as client:
            create = client.post("/api/saved-hotels", json=SAMPLE_PAYLOAD)
            self.assertEqual(create.status_code, 201)
            body = create.json()
            self.assertEqual(body["hotel_id"], "h1")
            self.assertEqual(len(body["nights"]), 5)

            ids = client.get("/api/saved-hotels/ids")
            self.assertEqual(ids.json(), ["h1"])

            for_zip = client.get("/api/saved-hotels", params={"zip": "16802"})
            self.assertEqual(for_zip.status_code, 200)
            self.assertEqual(len(for_zip.json()["hotels"]), 1)
            self.assertEqual(for_zip.json()["locality"], "State College")

            deleted = client.delete("/api/saved-hotels/h1")
            self.assertEqual(deleted.status_code, 204)

            ids_after = client.get("/api/saved-hotels/ids")
            self.assertEqual(ids_after.json(), [])
            for_zip_after = client.get("/api/saved-hotels", params={"zip": "16802"})
            self.assertEqual(for_zip_after.json()["hotels"], [])

    def test_repeated_save_via_route_is_idempotent(self):
        with TestClient(main.app) as client:
            client.post("/api/saved-hotels", json=SAMPLE_PAYLOAD)
            client.post("/api/saved-hotels", json=SAMPLE_PAYLOAD)
            ids = client.get("/api/saved-hotels/ids")
            self.assertEqual(ids.json(), ["h1"])

    def test_delete_unsaved_hotel_returns_404(self):
        with TestClient(main.app) as client:
            resp = client.delete("/api/saved-hotels/does-not-exist")
            self.assertEqual(resp.status_code, 404)

    def test_get_saved_hotels_invalid_zip_returns_422(self):
        with TestClient(main.app) as client:
            resp = client.get("/api/saved-hotels", params={"zip": "123"})
            self.assertEqual(resp.status_code, 422)

    def test_post_saved_hotel_invalid_zip_returns_422(self):
        with TestClient(main.app) as client:
            payload = {**SAMPLE_PAYLOAD, "zip": "abc"}
            resp = client.post("/api/saved-hotels", json=payload)
            self.assertEqual(resp.status_code, 422)

    def test_post_saved_hotel_invalid_latitude_returns_422(self):
        with TestClient(main.app) as client:
            payload = {**SAMPLE_PAYLOAD, "latitude": 999}
            resp = client.post("/api/saved-hotels", json=payload)
            self.assertEqual(resp.status_code, 422)

    def test_post_saved_hotel_invalid_longitude_returns_422(self):
        with TestClient(main.app) as client:
            payload = {**SAMPLE_PAYLOAD, "longitude": -200}
            resp = client.post("/api/saved-hotels", json=payload)
            self.assertEqual(resp.status_code, 422)

    def test_nullable_name_and_address_round_trip(self):
        with TestClient(main.app) as client:
            payload = {**SAMPLE_PAYLOAD, "name": None, "address": None}
            create = client.post("/api/saved-hotels", json=payload)
            self.assertEqual(create.status_code, 201)
            for_zip = client.get("/api/saved-hotels", params={"zip": "16802"})
            hotel = for_zip.json()["hotels"][0]
            self.assertIsNone(hotel["name"])
            self.assertIsNone(hotel["address"])


if __name__ == "__main__":
    unittest.main()
