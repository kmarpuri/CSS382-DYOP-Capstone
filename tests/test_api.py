"""FastAPI endpoint smoke tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from capstone.api import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestHealth:
    def test_health(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"

    def test_hardware(self, client):
        r = client.get("/api/hardware")
        assert r.status_code == 200
        body = r.json()
        assert body["tier"] in {1, 2, 3, 4}
        assert "recommended_model" in body


class TestUIServed:
    def test_root_serves_html(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "Capstone" in r.text
        assert "Local-only" in r.text or "no data leaves" in r.text


FIXTURE_PDF = Path(__file__).parent.parent / "UWUnofficialTranscript.pdf"


@pytest.mark.skipif(not FIXTURE_PDF.exists(), reason="fixture PDF not present")
class TestFullPipeline:
    def test_parse_then_recommend(self, client):
        # Parse the fixture PDF
        with open(FIXTURE_PDF, "rb") as f:
            r = client.post(
                "/api/parse-transcript",
                files={"file": ("t.pdf", f, "application/pdf")},
            )
        assert r.status_code == 200
        transcript = r.json()
        assert transcript["major"] == "CSSE"
        assert len(transcript["completed"]) > 0

        # Recommend (no LLM)
        r = client.post("/api/recommend", json={
            "transcript": transcript,
            "target_quarter": "AUT",
            "credit_load": 15,
            "top_n": 5,
            "use_llm": False,
        })
        assert r.status_code == 200
        result = r.json()
        assert 0 < result["total_credits"] <= 17
        assert len(result["recommendations"]) >= 1
        # No completed course should appear in the recommendations.
        completed_ids = {c["course_id"] for c in transcript["completed"]}
        rec_ids = {r["course_id"] for r in result["recommendations"]}
        assert not (completed_ids & rec_ids)
