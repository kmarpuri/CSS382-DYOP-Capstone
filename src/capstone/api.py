"""FastAPI server for the Capstone web UI.

Endpoints
---------
POST /api/parse-transcript     — upload a PDF, get the parsed Transcript JSON
POST /api/recommend            — body: parsed Transcript + load + quarter
GET  /api/courses              — search the catalog
GET  /api/major-requirements   — list requirements for a major
GET  /api/hardware             — hardware tier + recommended model
GET  /                         — serves the single-page UI

All routes operate against the local SQLite database. No transcript
data is ever sent off-device.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from capstone.config import PROJECT_ROOT, load_config
from capstone.db.connection import get_connection
from capstone.recommender import RecommendationResult, Recommender
from capstone.transcript import parse_transcript
from capstone.transcript.models import Transcript

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Capstone — UW Bothell Course Advisor",
    version="0.1.0",
    description="Local-only course recommendation engine. "
                "No data leaves the machine.",
)


def _db_path() -> Path:
    config = load_config()
    return config.database.resolve_path(PROJECT_ROOT)


# ── Models ──────────────────────────────────────────────────────────────

class RecommendRequest(BaseModel):
    transcript: Transcript
    target_quarter: str | None = Field(default=None, examples=["AUT", "WIN"])
    credit_load: int | None = Field(default=None, ge=1, le=25)
    top_n: int = Field(default=10, ge=1, le=50)
    use_llm: bool = True
    major_override: str | None = None


# ── Endpoints ───────────────────────────────────────────────────────────

@app.get("/api/health")
def health() -> dict:
    p = _db_path()
    return {
        "status": "ok",
        "db_exists": p.exists(),
        "db_path": str(p),
    }


@app.get("/api/hardware")
def hardware() -> dict:
    from capstone.llm.hardware import detect_hardware_tier

    tier = detect_hardware_tier()
    return {
        "tier": tier.tier,
        "ram_gb": round(tier.ram_gb, 1),
        "vram_gb": round(tier.vram_gb, 1),
        "recommended_model": tier.model,
        "notes": tier.notes,
    }


@app.get("/api/llm-status")
def llm_status() -> dict:
    """Snapshot of the local LLM stack — used by the UI's first-run banner."""
    from capstone.firstrun import (
        installed_models,
        is_first_run,
        ollama_binary_present,
        ollama_daemon_running,
    )
    from capstone.llm.hardware import detect_hardware_tier

    hw = detect_hardware_tier()
    return {
        "first_run": is_first_run(),
        "ollama_installed": ollama_binary_present(),
        "ollama_running": ollama_daemon_running(),
        "installed_models": installed_models(),
        "recommended_model": hw.model,
        "tier": hw.tier,
    }


@app.post("/api/parse-transcript")
async def api_parse_transcript(file: UploadFile = File(...)) -> Transcript:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Expected a PDF file")

    data = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
        tmp.write(data)
        tmp.flush()
        try:
            transcript = parse_transcript(tmp.name)
        except Exception as e:
            logger.exception("Transcript parsing failed")
            raise HTTPException(500, f"Could not parse transcript: {e}")

    return transcript


@app.post("/api/recommend")
def api_recommend(req: RecommendRequest) -> RecommendationResult:
    config = load_config()
    db_path = _db_path()
    if not db_path.exists():
        raise HTTPException(503, "Course database not initialized. Run 'capstone scrape refresh'.")

    transcript = req.transcript
    if req.major_override:
        transcript.major = req.major_override

    credit_load = req.credit_load or config.credit_limits.default

    with get_connection(db_path) as conn:
        recommender = Recommender(conn, config)
        result = recommender.recommend(
            transcript=transcript,
            target_quarter=req.target_quarter,
            credit_load=credit_load,
            top_n=req.top_n,
            use_llm=req.use_llm,
        )
    return result


@app.get("/api/courses")
def list_courses(
    q: Annotated[str | None, Query(description="Search query (course_id or title)")] = None,
    department: str | None = None,
    limit: int = 50,
) -> list[dict]:
    config = load_config()
    db_path = _db_path()
    if not db_path.exists():
        raise HTTPException(503, "Course database not initialized.")

    with get_connection(db_path) as conn:
        sql = "SELECT course_id, title, credits, department, offering_pattern FROM courses WHERE 1=1"
        params: list = []
        if q:
            sql += " AND (course_id LIKE ? OR title LIKE ?)"
            params.extend([f"%{q.upper()}%", f"%{q}%"])
        if department:
            sql += " AND department = ?"
            params.append(department.upper())
        sql += " ORDER BY course_id LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


@app.get("/api/major-requirements")
def major_requirements(major: str = "CSSE") -> list[dict]:
    db_path = _db_path()
    if not db_path.exists():
        raise HTTPException(503, "Course database not initialized.")
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT category, course_id, required_count, group_id, notes "
            "FROM major_requirements WHERE major = ? "
            "ORDER BY category, group_id, course_id",
            (major.upper(),),
        ).fetchall()
        return [dict(r) for r in rows]


# ── UI ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def ui_root() -> str:
    """Serve the single-page UI bundled inside the package."""
    ui_html = Path(__file__).parent / "ui" / "index.html"
    if ui_html.exists():
        return ui_html.read_text(encoding="utf-8")
    return _FALLBACK_HTML


_FALLBACK_HTML = """\
<!doctype html><html><body style="font-family: system-ui; padding: 2rem;">
<h1>Capstone API is running</h1>
<p>The bundled UI HTML was not found. Hit
<a href="/docs">/docs</a> for the API reference.</p>
</body></html>
"""
