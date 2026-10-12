import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import chat
import models

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "chat_sample.json"


class ChatTests(unittest.TestCase):
    """Tests for chat.py, run against a fresh temporary SQLite file per
    test — never the real backend/travel.db. The LLM is always mocked
    (patch("chat._call_openrouter", ...)) — no live OpenRouter calls."""

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

    def _seed(self, hotel_id="h1", zip_code="16802"):
        conn = models.get_connection()
        conn.execute(
            "INSERT INTO saved_hotels (hotel_id, name, address, latitude, longitude) "
            "VALUES (?, 'Test Hotel', '1 Main St', 40.8, -77.86)",
            (hotel_id,),
        )
        conn.execute(
            "INSERT INTO saved_hotel_zip_searches (hotel_id, zip, locality, center_latitude, center_longitude) "
            "VALUES (?, ?, 'State College', 40.8, -77.86)",
            (hotel_id, zip_code),
        )
        conn.execute(
            "INSERT INTO demo_hotel_nights (hotel_id, stay_date, nightly_rate_cents, rooms_available) "
            "VALUES (?, '2026-10-10', 10000, 20)",
            (hotel_id,),
        )
        conn.commit()
        conn.close()

    # --- SQL validation (no LLM involved at all) ---

    def test_disallowed_delete_query_is_rejected_and_db_is_unchanged(self):
        self._seed()
        with self.assertRaises(chat.SQLRejectedError):
            chat.validate_and_run_sql("DELETE FROM saved_hotels")

        conn = models.get_connection()
        count = conn.execute("SELECT COUNT(*) FROM saved_hotels").fetchone()[0]
        conn.close()
        self.assertEqual(count, 1, "DELETE must not have executed")

    def test_disallowed_drop_query_is_rejected_and_db_is_unchanged(self):
        self._seed()
        with self.assertRaises(chat.SQLRejectedError):
            chat.validate_and_run_sql("DROP TABLE saved_hotels")

        conn = models.get_connection()
        count = conn.execute("SELECT COUNT(*) FROM saved_hotels").fetchone()[0]
        conn.close()
        self.assertEqual(count, 1, "DROP must not have executed")

    def test_disallowed_update_query_is_rejected_and_db_is_unchanged(self):
        self._seed()
        with self.assertRaises(chat.SQLRejectedError):
            chat.validate_and_run_sql("UPDATE saved_hotels SET name = 'hacked'")

        conn = models.get_connection()
        name = conn.execute("SELECT name FROM saved_hotels WHERE hotel_id = 'h1'").fetchone()[0]
        conn.close()
        self.assertEqual(name, "Test Hotel", "UPDATE must not have executed")

    def test_multi_statement_query_is_rejected(self):
        self._seed()
        with self.assertRaises(chat.SQLRejectedError):
            chat.validate_and_run_sql("SELECT * FROM saved_hotels; DROP TABLE saved_hotels;")

        conn = models.get_connection()
        count = conn.execute("SELECT COUNT(*) FROM saved_hotels").fetchone()[0]
        conn.close()
        self.assertEqual(count, 1, "the DROP half of the multi-statement must not have executed")

    def test_query_touching_other_table_is_rejected(self):
        self._seed()
        with self.assertRaises(chat.SQLRejectedError):
            chat.validate_and_run_sql("SELECT * FROM hotels")

    def test_non_select_statement_shape_is_rejected(self):
        with self.assertRaises(chat.SQLRejectedError):
            chat.validate_and_run_sql("PRAGMA table_info(saved_hotels)")

    def test_missing_limit_is_added(self):
        self._seed()
        final_sql, rows = chat.validate_and_run_sql("SELECT * FROM saved_hotels")
        self.assertIn("LIMIT 50", final_sql)
        self.assertEqual(len(rows), 1)

    def test_oversized_limit_is_capped(self):
        self._seed()
        final_sql, _rows = chat.validate_and_run_sql("SELECT * FROM saved_hotels LIMIT 500")
        self.assertIn("LIMIT 50", final_sql)
        self.assertNotIn("LIMIT 500", final_sql)

    def test_with_select_cte_is_allowed(self):
        self._seed()
        final_sql, rows = chat.validate_and_run_sql(
            "WITH x AS (SELECT * FROM saved_hotels) SELECT * FROM x"
        )
        self.assertEqual(len(rows), 1)

    # --- LLM-mocked flows ---

    @patch("chat._call_openrouter")
    def test_llm_failure_raises_llm_request_error(self, mock_llm):
        mock_llm.side_effect = chat.LLMRequestError("boom")
        with self.assertRaises(chat.LLMRequestError):
            chat.answer_question("Any question?")

    @patch("chat._call_openrouter")
    def test_rate_limit_raises_distinct_error(self, mock_llm):
        mock_llm.side_effect = chat.LLMRateLimitedError("rate limited")
        with self.assertRaises(chat.LLMRateLimitedError):
            chat.answer_question("Any question?")

    @patch("chat._call_openrouter")
    def test_no_match_question_returns_no_match_status_without_second_llm_call(self, mock_llm):
        self._seed()
        # Proposes a valid, well-formed query that simply matches nothing.
        mock_llm.return_value = "SELECT * FROM saved_hotels WHERE hotel_id = 'does-not-exist'"

        result = chat.answer_question("Tell me about a hotel that isn't saved")

        self.assertEqual(result["status"], "no_match")
        self.assertEqual(result["rows"], [])
        mock_llm.assert_called_once()  # only the SQL-generation call, no second (answer) call

    @patch("chat._call_openrouter")
    def test_golden_path_matches_fixture(self, mock_llm):
        """Loads tests/fixtures/chat_sample.json, seeds its data, mocks
        both LLM calls with its fixed responses, and checks the full
        response against its expected_response."""
        with open(FIXTURE_PATH) as f:
            fixture = json.load(f)

        conn = models.get_connection()
        for row in fixture["seed_data"]["saved_hotels"]:
            conn.execute(
                "INSERT INTO saved_hotels (hotel_id, name, address, latitude, longitude) "
                "VALUES (:hotel_id, :name, :address, :latitude, :longitude)",
                row,
            )
        for row in fixture["seed_data"]["saved_hotel_zip_searches"]:
            conn.execute(
                "INSERT INTO saved_hotel_zip_searches "
                "(hotel_id, zip, locality, center_latitude, center_longitude) "
                "VALUES (:hotel_id, :zip, :locality, :center_latitude, :center_longitude)",
                row,
            )
        for row in fixture["seed_data"]["demo_hotel_nights"]:
            conn.execute(
                "INSERT INTO demo_hotel_nights (hotel_id, stay_date, nightly_rate_cents, rooms_available) "
                "VALUES (:hotel_id, :stay_date, :nightly_rate_cents, :rooms_available)",
                row,
            )
        conn.commit()
        conn.close()

        mock_llm.side_effect = [fixture["mocked_sql_response"], fixture["mocked_answer_response"]]

        result = chat.answer_question(fixture["question"])

        expected = fixture["expected_response"]
        self.assertEqual(result["proposed_sql"], expected["proposed_sql"])
        self.assertEqual(result["rows"], expected["rows"])
        self.assertEqual(result["answer"], expected["answer"])
        self.assertEqual(result["status"], expected["status"])


if __name__ == "__main__":
    unittest.main()
