import os
import tempfile
import unittest

import models
import saved_hotels


class SavedHotelsTests(unittest.TestCase):
    """Mutation tests for saved_hotels.py, run against a fresh temporary
    SQLite file per test — never the real backend/travel.db."""

    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._tmp_path = tmp.name
        self._original_db_path = models.DB_PATH
        models.DB_PATH = self._tmp_path
        models.init_db()

    def tearDown(self):
        models.DB_PATH = self._original_db_path
        os.unlink(self._tmp_path)

    def test_save_hotel_creates_zip_association_and_five_demo_nights(self):
        result = saved_hotels.save_hotel(
            hotel_id="h1",
            name="Test Hotel",
            address="1 Main St",
            latitude=40.8,
            longitude=-77.86,
            zip_code="16802",
            locality="State College",
        )

        self.assertEqual(result["hotel_id"], "h1")
        self.assertEqual(len(result["nights"]), 5)
        self.assertEqual(
            [n["stay_date"] for n in result["nights"]],
            ["2026-10-10", "2026-10-11", "2026-10-12", "2026-10-13", "2026-10-14"],
        )
        self.assertTrue(all(n["nightly_rate_cents"] == 10000 for n in result["nights"]))
        self.assertTrue(all(n["rooms_available"] == 20 for n in result["nights"]))

        self.assertEqual(saved_hotels.list_saved_hotel_ids(), ["h1"])

        for_zip = saved_hotels.list_saved_hotels_for_zip("16802")
        self.assertEqual(for_zip["locality"], "State College")
        self.assertEqual(len(for_zip["hotels"]), 1)

    def test_repeated_save_does_not_duplicate_rows_or_overwrite_rates(self):
        saved_hotels.save_hotel("h1", "Test Hotel", "1 Main St", 40.8, -77.86, "16802", "State College")

        # Simulate a rate that has since diverged from the default — a
        # re-save must not stomp this back to 10000.
        conn = models.get_connection()
        conn.execute(
            "UPDATE demo_hotel_nights SET nightly_rate_cents = 5000 "
            "WHERE hotel_id = 'h1' AND stay_date = '2026-10-10'"
        )
        conn.commit()
        conn.close()

        saved_hotels.save_hotel("h1", "Different Name", "Different Addr", 1, 1, "16802", "Different Locality")

        self.assertEqual(saved_hotels.list_saved_hotel_ids(), ["h1"])
        hotels = saved_hotels.list_saved_hotels_for_zip("16802")["hotels"]
        self.assertEqual(len(hotels), 1)
        night = next(n for n in hotels[0]["nights"] if n["stay_date"] == "2026-10-10")
        self.assertEqual(night["nightly_rate_cents"], 5000)

        conn = models.get_connection()
        night_count = conn.execute(
            "SELECT COUNT(*) FROM demo_hotel_nights WHERE hotel_id = 'h1'"
        ).fetchone()[0]
        assoc_count = conn.execute(
            "SELECT COUNT(*) FROM saved_hotel_zip_searches WHERE hotel_id = 'h1' AND zip = '16802'"
        ).fetchone()[0]
        conn.close()
        self.assertEqual(night_count, 5)
        self.assertEqual(assoc_count, 1)

    def test_same_hotel_saved_under_a_second_zip_adds_association_not_duplicate_hotel(self):
        saved_hotels.save_hotel("h1", "Test Hotel", "1 Main St", 40.8, -77.86, "16802", "State College")
        saved_hotels.save_hotel("h1", "Test Hotel", "1 Main St", 40.8, -77.86, "16801", "State College")

        self.assertEqual(saved_hotels.list_saved_hotel_ids(), ["h1"])
        self.assertEqual(len(saved_hotels.list_saved_hotels_for_zip("16802")["hotels"]), 1)
        self.assertEqual(len(saved_hotels.list_saved_hotels_for_zip("16801")["hotels"]), 1)

    def test_list_saved_hotels_for_unmatched_zip_is_empty_not_an_error(self):
        result = saved_hotels.list_saved_hotels_for_zip("00000")
        self.assertEqual(result["hotels"], [])
        self.assertIsNone(result["locality"])
        self.assertIsNone(result["latitude"])
        self.assertIsNone(result["longitude"])

    def test_local_results_response_shape_includes_center_coordinates(self):
        """Regression test for the blank-map bug: the local-results
        response must carry latitude/longitude the frontend can hand
        straight to Leaflet, not just zip/locality/hotels."""
        saved_hotels.save_hotel(
            "h1", "Test Hotel", "1 Main St", 40.81, -77.85,
            "16802", "State College", center_latitude=40.8, center_longitude=-77.86,
        )

        result = saved_hotels.list_saved_hotels_for_zip("16802")

        self.assertEqual(set(result.keys()), {"zip", "locality", "latitude", "longitude", "hotels"})
        self.assertEqual(result["latitude"], 40.8)
        self.assertEqual(result["longitude"], -77.86)
        self.assertEqual(set(result["hotels"][0].keys()), {"hotel_id", "name", "address", "latitude", "longitude", "nights"})

    def test_list_saved_hotels_falls_back_to_hotel_centroid_when_center_missing(self):
        """Simulates a row saved before center_latitude/center_longitude
        existed (both NULL) — must not crash, and must centre on the
        saved hotels themselves rather than return null coordinates."""
        saved_hotels.save_hotel(
            "h1", "Hotel One", "Addr 1", 10.0, 20.0,
            "16802", "State College", center_latitude=None, center_longitude=None,
        )
        saved_hotels.save_hotel(
            "h2", "Hotel Two", "Addr 2", 12.0, 22.0,
            "16802", "State College", center_latitude=None, center_longitude=None,
        )

        result = saved_hotels.list_saved_hotels_for_zip("16802")

        self.assertIsNotNone(result["latitude"])
        self.assertIsNotNone(result["longitude"])
        self.assertAlmostEqual(result["latitude"], 11.0)
        self.assertAlmostEqual(result["longitude"], 21.0)

    def test_migration_adds_center_columns_to_a_pre_existing_table(self):
        """Simulates a database created before center_latitude/
        center_longitude existed: an old-style saved_hotel_zip_searches
        table with real data in it. init_db() must add the columns
        without erroring and without losing that data, and running it
        again must be a safe no-op (repeatable migration)."""
        conn = models.get_connection()
        conn.executescript(
            """
            DROP TABLE saved_hotel_zip_searches;
            CREATE TABLE saved_hotel_zip_searches (
                hotel_id TEXT NOT NULL REFERENCES saved_hotels(hotel_id),
                zip TEXT NOT NULL,
                locality TEXT,
                PRIMARY KEY (hotel_id, zip)
            );
            """
        )
        conn.execute(
            "INSERT INTO saved_hotels (hotel_id, name, address, latitude, longitude) "
            "VALUES ('legacy1', 'Legacy Hotel', 'Old Addr', 5.0, 6.0)"
        )
        conn.execute(
            "INSERT INTO saved_hotel_zip_searches (hotel_id, zip, locality) "
            "VALUES ('legacy1', '16802', 'State College')"
        )
        conn.commit()
        conn.close()

        # Run the migration twice — must be idempotent.
        models.init_db()
        models.init_db()

        result = saved_hotels.list_saved_hotels_for_zip("16802")
        self.assertEqual(len(result["hotels"]), 1)
        self.assertEqual(result["hotels"][0]["hotel_id"], "legacy1")
        # No center was ever recorded for this legacy row -> centroid fallback.
        self.assertEqual(result["latitude"], 5.0)
        self.assertEqual(result["longitude"], 6.0)

    def test_delete_removes_hotel_associations_and_nights_together(self):
        saved_hotels.save_hotel("h1", "Test Hotel", "1 Main St", 40.8, -77.86, "16802", "State College")

        saved_hotels.delete_saved_hotel("h1")

        self.assertEqual(saved_hotels.list_saved_hotel_ids(), [])
        self.assertEqual(saved_hotels.list_saved_hotels_for_zip("16802")["hotels"], [])

        conn = models.get_connection()
        nights_left = conn.execute(
            "SELECT COUNT(*) FROM demo_hotel_nights WHERE hotel_id = 'h1'"
        ).fetchone()[0]
        assoc_left = conn.execute(
            "SELECT COUNT(*) FROM saved_hotel_zip_searches WHERE hotel_id = 'h1'"
        ).fetchone()[0]
        conn.close()
        self.assertEqual(nights_left, 0)
        self.assertEqual(assoc_left, 0)

    def test_delete_unsaved_hotel_raises(self):
        with self.assertRaises(saved_hotels.HotelNotSavedError):
            saved_hotels.delete_saved_hotel("does-not-exist")

    def test_delete_preserves_unrelated_saved_hotel(self):
        saved_hotels.save_hotel("h1", "Hotel One", "Addr 1", 1, 1, "16802", "Loc")
        saved_hotels.save_hotel("h2", "Hotel Two", "Addr 2", 2, 2, "16802", "Loc")

        saved_hotels.delete_saved_hotel("h1")

        self.assertEqual(saved_hotels.list_saved_hotel_ids(), ["h2"])

    def test_assignment1_tables_are_seeded_and_untouched_by_this_feature(self):
        conn = models.get_connection()
        hotel_count = conn.execute("SELECT COUNT(*) FROM hotels").fetchone()[0]
        trip_count = conn.execute("SELECT COUNT(*) FROM trips").fetchone()[0]
        conn.close()
        self.assertGreater(hotel_count, 0)
        self.assertGreater(trip_count, 0)


if __name__ == "__main__":
    unittest.main()
