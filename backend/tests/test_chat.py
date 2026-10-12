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

    def _load_fixture_examples(self):
        with open(FIXTURE_PATH) as f:
            return json.load(f)["examples"]

    def _seed_fixture_data(self, seed_data):
        conn = models.get_connection()
        for row in seed_data.get("saved_hotels", []):
            conn.execute(
                "INSERT INTO saved_hotels (hotel_id, name, address, latitude, longitude) "
                "VALUES (:hotel_id, :name, :address, :latitude, :longitude)",
                row,
            )
        for row in seed_data.get("saved_hotel_zip_searches", []):
            conn.execute(
                "INSERT INTO saved_hotel_zip_searches "
                "(hotel_id, zip, locality, center_latitude, center_longitude) "
                "VALUES (:hotel_id, :zip, :locality, :center_latitude, :center_longitude)",
                row,
            )
        for row in seed_data.get("demo_hotel_nights", []):
            conn.execute(
                "INSERT INTO demo_hotel_nights (hotel_id, stay_date, nightly_rate_cents, rooms_available) "
                "VALUES (:hotel_id, :stay_date, :nightly_rate_cents, :rooms_available)",
                row,
            )
        conn.commit()
        conn.close()

    @patch("chat._call_openrouter")
    def test_fixture_answer_example_matches_expected(self, mock_llm):
        """Loads the "answer" example from tests/fixtures/chat_sample.json,
        seeds its data, mocks both LLM calls with its fixed responses, and
        checks the full response against its expected_response."""
        example = self._load_fixture_examples()["answer"]
        self._seed_fixture_data(example["seed_data"])
        mock_llm.side_effect = [example["mocked_sql_response"], example["mocked_answer_response"]]

        result = chat.answer_question(example["question"])

        expected = example["expected_response"]
        self.assertEqual(result["proposed_sql"], expected["proposed_sql"])
        self.assertEqual(result["rows"], expected["rows"])
        self.assertEqual(result["answer"], expected["answer"])
        self.assertEqual(result["status"], expected["status"])

    @patch("chat._call_openrouter")
    def test_fixture_no_match_example_matches_expected(self, mock_llm):
        example = self._load_fixture_examples()["no_match"]
        self._seed_fixture_data(example.get("seed_data", {}))
        mock_llm.return_value = example["mocked_sql_response"]

        result = chat.answer_question(example["question"])

        expected = example["expected_response"]
        self.assertEqual(result["status"], expected["status"])
        self.assertEqual(result["rows"], expected["rows"])
        self.assertEqual(result["answer"], expected["answer"])
        mock_llm.assert_called_once()

    @patch("chat._call_openrouter")
    def test_fixture_insufficient_data_example_matches_expected(self, mock_llm):
        example = self._load_fixture_examples()["insufficient_data"]
        mock_llm.return_value = example["mocked_sql_response"]

        with patch("chat.validate_and_run_sql") as mock_run:
            result = chat.answer_question(example["question"])
            mock_run.assert_not_called()

        expected = example["expected_response"]
        self.assertEqual(result["status"], expected["status"])
        self.assertEqual(result["proposed_sql"], expected["proposed_sql"])
        self.assertEqual(result["answer"], expected["answer"])
        mock_llm.assert_called_once()

    @patch("chat._call_openrouter")
    def test_fixture_rejected_example_matches_expected(self, mock_llm):
        example = self._load_fixture_examples()["rejected"]
        mock_llm.return_value = example["mocked_sql_response"]

        with self.assertRaises(chat.SQLRejectedError) as ctx:
            chat.answer_question(example["question"])

        self.assertEqual(ctx.exception.proposed_sql, example["expected_proposed_sql"])

    @patch("chat._call_openrouter")
    def test_fixture_unclear_example_matches_expected(self, mock_llm):
        example = self._load_fixture_examples()["unclear"]
        mock_llm.return_value = example["mocked_sql_response"]

        with patch("chat.validate_and_run_sql") as mock_run:
            result = chat.answer_question(example["question"])
            mock_run.assert_not_called()

        expected = example["expected_response"]
        self.assertEqual(result["status"], expected["status"])
        self.assertEqual(result["proposed_sql"], expected["proposed_sql"])
        self.assertEqual(result["answer"], expected["answer"])
        mock_llm.assert_called_once()

    # --- Incident fixes: grounding and state problems from manual testing ---

    @patch("chat._call_openrouter")
    def test_cheapest_multi_night_excludes_hotel_missing_a_night_and_sums_correctly(self, mock_llm):
        conn = models.get_connection()
        for hotel_id, name in (("h1", "Cheap Inn"), ("h2", "Partial Inn"), ("h3", "Pricier Inn")):
            conn.execute(
                "INSERT INTO saved_hotels (hotel_id, name, address, latitude, longitude) "
                "VALUES (?, ?, '1 Main St', 37.58, -122.38)",
                (hotel_id, name),
            )
            conn.execute(
                "INSERT INTO saved_hotel_zip_searches (hotel_id, zip, locality, center_latitude, center_longitude) "
                "VALUES (?, '94010', 'Burlingame', 37.58, -122.38)",
                (hotel_id,),
            )
        # h1: available both requested nights at $80/night -> $160 total.
        conn.execute(
            "INSERT INTO demo_hotel_nights (hotel_id, stay_date, nightly_rate_cents, rooms_available) "
            "VALUES ('h1', '2026-10-10', 8000, 20)"
        )
        conn.execute(
            "INSERT INTO demo_hotel_nights (hotel_id, stay_date, nightly_rate_cents, rooms_available) "
            "VALUES ('h1', '2026-10-11', 8000, 20)"
        )
        # h2: missing 2026-10-11 entirely -> must be excluded, never "cheaper".
        conn.execute(
            "INSERT INTO demo_hotel_nights (hotel_id, stay_date, nightly_rate_cents, rooms_available) "
            "VALUES ('h2', '2026-10-10', 7000, 20)"
        )
        # h3: available both nights, but pricier than h1 -> still qualifies.
        conn.execute(
            "INSERT INTO demo_hotel_nights (hotel_id, stay_date, nightly_rate_cents, rooms_available) "
            "VALUES ('h3', '2026-10-10', 9000, 20)"
        )
        conn.execute(
            "INSERT INTO demo_hotel_nights (hotel_id, stay_date, nightly_rate_cents, rooms_available) "
            "VALUES ('h3', '2026-10-11', 9000, 20)"
        )
        conn.commit()
        conn.close()

        proposed_sql = (
            "WITH nights AS ("
            "SELECT z.hotel_id, h.name, h.address, n.stay_date, n.nightly_rate_cents, n.rooms_available "
            "FROM saved_hotel_zip_searches z "
            "JOIN saved_hotels h ON h.hotel_id = z.hotel_id "
            "JOIN demo_hotel_nights n ON n.hotel_id = z.hotel_id "
            "WHERE z.zip = '94010' AND n.stay_date IN ('2026-10-10', '2026-10-11') AND n.rooms_available > 0"
            "), totals AS ("
            "SELECT hotel_id, name, address, COUNT(*) AS nights_found, SUM(nightly_rate_cents) AS total_cost_cents "
            "FROM nights GROUP BY hotel_id, name, address HAVING COUNT(*) = 2"
            ") "
            "SELECT nights.hotel_id, nights.name, nights.address, nights.stay_date, "
            "nights.nightly_rate_cents, nights.rooms_available, totals.nights_found, totals.total_cost_cents "
            "FROM nights JOIN totals ON totals.hotel_id = nights.hotel_id "
            "ORDER BY totals.total_cost_cents ASC, nights.hotel_id, nights.stay_date"
        )
        mock_llm.side_effect = [proposed_sql, "Hotel: Cheap Inn\nTotal cost: $160\nReason: cheapest qualifying hotel"]

        result = chat.answer_question("Cheapest saved hotel in 94010 for Oct 10-12?")

        self.assertEqual(result["status"], "answer")
        hotel_ids = {row["hotel_id"] for row in result["rows"]}
        self.assertEqual(hotel_ids, {"h1", "h3"}, "hotel missing a requested night must be excluded")

        h1_rows = [row for row in result["rows"] if row["hotel_id"] == "h1"]
        self.assertEqual(len(h1_rows), 2)
        self.assertTrue(all(row["total_cost_cents"] == 16000 for row in h1_rows), "160 * 100 cents")
        self.assertTrue(all(row["nights_found"] == 2 for row in h1_rows))

        self.assertEqual(mock_llm.call_count, 2, "stage 2 must be called with the real qualifying rows")
        answer_call_messages = mock_llm.call_args_list[1][0][0]
        answer_payload = json.dumps(answer_call_messages)
        self.assertIn("h1", answer_payload)
        self.assertIn("h3", answer_payload, "all qualifying hotels must reach stage 2, not just the cheapest")
        self.assertNotIn("h2", answer_payload, "the hotel missing a requested night must not reach stage 2")

    @patch("chat._call_openrouter")
    def test_airport_distance_question_returns_insufficient_data_without_running_sql(self, mock_llm):
        self._seed()
        mock_llm.return_value = (
            "INSUFFICIENT_DATA: the database has no airport or landmark locations to measure distance from"
        )

        with patch("chat.validate_and_run_sql") as mock_run:
            result = chat.answer_question("Which saved hotel is closest to SFO airport?")
            mock_run.assert_not_called()

        self.assertEqual(result["status"], "insufficient_data")
        self.assertEqual(result["rows"], [])
        self.assertIsNone(result["proposed_sql"])
        mock_llm.assert_called_once()

    @patch("chat._call_openrouter")
    def test_delete_request_is_refused_via_sentinel_without_running_sql(self, mock_llm):
        self._seed()
        mock_llm.return_value = "READ_ONLY_REFUSAL"

        with patch("chat.validate_and_run_sql") as mock_run:
            with self.assertRaises(chat.ReadOnlyRefusalError):
                chat.answer_question("Delete all saved hotels")
            mock_run.assert_not_called()

        conn = models.get_connection()
        count = conn.execute("SELECT COUNT(*) FROM saved_hotels").fetchone()[0]
        conn.close()
        self.assertEqual(count, 1, "DB must be unchanged by a refused delete request")

    @patch("chat._call_openrouter")
    def test_unrelated_input_returns_unclear_without_running_sql(self, mock_llm):
        mock_llm.return_value = "UNCLEAR"

        with patch("chat.validate_and_run_sql") as mock_run:
            result = chat.answer_question("Then, in DB Browser")
            mock_run.assert_not_called()

        self.assertEqual(result["status"], "unclear")
        self.assertIsNone(result["proposed_sql"])
        mock_llm.assert_called_once()


if __name__ == "__main__":
    unittest.main()
