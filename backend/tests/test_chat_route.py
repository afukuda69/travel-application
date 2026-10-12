import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import chat
import main
import models


class ChatRouteTests(unittest.TestCase):
    """Route-level tests for POST /api/chat, run against a fresh temporary
    SQLite file per test — never the real backend/travel.db. The LLM is
    always mocked — no live OpenRouter calls."""

    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._tmp_path = tmp.name
        self._patcher = patch.object(models, "DB_PATH", self._tmp_path)
        self._patcher.start()
        models.init_db()

    def tearDown(self):
        self._patcher.stop()
        os.unlink(self._tmp_path)

    def _seed(self):
        conn = models.get_connection()
        conn.execute(
            "INSERT INTO saved_hotels (hotel_id, name, address, latitude, longitude) "
            "VALUES ('h1', 'Test Hotel', '1 Main St', 40.8, -77.86)"
        )
        conn.execute(
            "INSERT INTO saved_hotel_zip_searches (hotel_id, zip, locality, center_latitude, center_longitude) "
            "VALUES ('h1', '16802', 'State College', 40.8, -77.86)"
        )
        conn.execute(
            "INSERT INTO demo_hotel_nights (hotel_id, stay_date, nightly_rate_cents, rooms_available) "
            "VALUES ('h1', '2026-10-10', 10000, 20)"
        )
        conn.commit()
        conn.close()

    @patch("chat._call_openrouter")
    def test_disallowed_query_returns_rejected_and_db_is_unchanged(self, mock_llm):
        self._seed()
        mock_llm.return_value = "DROP TABLE saved_hotels"

        with TestClient(main.app) as client:
            resp = client.post("/api/chat", json={"question": "anything"})

        self.assertEqual(resp.status_code, 422)
        body = resp.json()
        self.assertEqual(body["status"], "rejected")
        self.assertIn("read-only", body["answer"].lower())
        self.assertEqual(body["rows"], [])

        conn = models.get_connection()
        count = conn.execute("SELECT COUNT(*) FROM saved_hotels").fetchone()[0]
        conn.close()
        self.assertEqual(count, 1, "the DROP must not have executed")

    @patch("chat._call_openrouter")
    def test_multi_statement_query_returns_rejected(self, mock_llm):
        self._seed()
        mock_llm.return_value = "SELECT * FROM saved_hotels; DELETE FROM saved_hotels;"

        with TestClient(main.app) as client:
            resp = client.post("/api/chat", json={"question": "anything"})

        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.json()["status"], "rejected")

        conn = models.get_connection()
        count = conn.execute("SELECT COUNT(*) FROM saved_hotels").fetchone()[0]
        conn.close()
        self.assertEqual(count, 1)

    @patch("chat._call_openrouter")
    def test_llm_failure_returns_error_status(self, mock_llm):
        mock_llm.side_effect = chat.LLMRequestError("boom")

        with TestClient(main.app) as client:
            resp = client.post("/api/chat", json={"question": "anything"})

        self.assertEqual(resp.status_code, 502)
        self.assertEqual(resp.json()["status"], "error")

    @patch("chat._call_openrouter")
    def test_rate_limit_returns_429_and_error_status(self, mock_llm):
        mock_llm.side_effect = chat.LLMRateLimitedError("rate limited")

        with TestClient(main.app) as client:
            resp = client.post("/api/chat", json={"question": "anything"})

        self.assertEqual(resp.status_code, 429)
        self.assertEqual(resp.json()["status"], "error")

    @patch("chat._call_openrouter")
    def test_not_configured_returns_503_and_error_status(self, mock_llm):
        mock_llm.side_effect = chat.LLMNotConfiguredError("not configured")

        with TestClient(main.app) as client:
            resp = client.post("/api/chat", json={"question": "anything"})

        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.json()["status"], "error")

    @patch("chat._call_openrouter")
    def test_no_match_question_returns_200_and_no_match_status(self, mock_llm):
        self._seed()
        mock_llm.return_value = "SELECT * FROM saved_hotels WHERE hotel_id = 'does-not-exist'"

        with TestClient(main.app) as client:
            resp = client.post("/api/chat", json={"question": "anything"})

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "no_match")

    @patch("chat._call_openrouter")
    def test_successful_answer_returns_full_shape(self, mock_llm):
        self._seed()
        mock_llm.side_effect = [
            "SELECT name, stay_date, nightly_rate_cents, rooms_available FROM saved_hotels "
            "JOIN demo_hotel_nights USING (hotel_id) WHERE hotel_id = 'h1'",
            "Test Hotel is $100.00/night on 2026-10-10, 20 rooms available.",
        ]

        with TestClient(main.app) as client:
            resp = client.post("/api/chat", json={"question": "What's the rate at Test Hotel?"})

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "answer")
        self.assertEqual(set(body.keys()), {"question", "proposed_sql", "rows", "answer", "status"})
        self.assertEqual(len(body["rows"]), 1)

    def test_empty_question_returns_422(self):
        with TestClient(main.app) as client:
            resp = client.post("/api/chat", json={"question": ""})
        self.assertEqual(resp.status_code, 422)

    @patch("chat._call_openrouter")
    def test_insufficient_data_sentinel_returns_200_and_insufficient_data_status(self, mock_llm):
        mock_llm.return_value = "INSUFFICIENT_DATA: no airport or landmark locations in the database"

        with TestClient(main.app) as client:
            resp = client.post("/api/chat", json={"question": "Which saved hotel is closest to SFO airport?"})

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "insufficient_data")
        self.assertIsNone(body["proposed_sql"])
        self.assertEqual(body["rows"], [])

    @patch("chat._call_openrouter")
    def test_read_only_refusal_sentinel_returns_422_rejected_and_db_unchanged(self, mock_llm):
        self._seed()
        mock_llm.return_value = "READ_ONLY_REFUSAL"

        with TestClient(main.app) as client:
            resp = client.post("/api/chat", json={"question": "Delete all saved hotels"})

        self.assertEqual(resp.status_code, 422)
        body = resp.json()
        self.assertEqual(body["status"], "rejected")
        self.assertIn("read-only", body["answer"].lower())
        self.assertEqual(body["rows"], [])

        conn = models.get_connection()
        count = conn.execute("SELECT COUNT(*) FROM saved_hotels").fetchone()[0]
        conn.close()
        self.assertEqual(count, 1, "a refused delete request must not change the database")

    @patch("chat._call_openrouter")
    def test_unclear_sentinel_returns_200_and_unclear_status(self, mock_llm):
        mock_llm.return_value = "UNCLEAR"

        with TestClient(main.app) as client:
            resp = client.post("/api/chat", json={"question": "Then, in DB Browser"})

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "unclear")
        self.assertIsNone(body["proposed_sql"])
        self.assertEqual(body["rows"], [])


if __name__ == "__main__":
    unittest.main()
