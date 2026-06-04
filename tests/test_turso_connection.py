"""Tests for the Turso / libSQL connection wrapper.

The deployed app runs on a hosted libSQL (Turso) database instead of a
local SQLite file. libSQL's driver returns plain tuples, but the whole
codebase assumes ``sqlite3.Row`` semantics (``row["col"]`` and
``dict(row)``). The wrapper in ``capstone.db.connection`` bridges that
gap. These tests pin the bridge down using a *local* libSQL connection
(no network/sync), so they run fully offline.

If the ``libsql`` driver isn't installed (it's an optional ``turso``
extra), the whole module is skipped.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest
from capstone.db.connection import _LibsqlConnection, _LibsqlRow, using_turso
from capstone.db.schema import init_db
from capstone.scrapers.ratemyprofessor import lookup_ratings

libsql = pytest.importorskip("libsql")


@pytest.fixture
def turso_conn(tmp_path):
    """A libSQL-backed connection in local-only mode (no sync_url)."""
    raw = libsql.connect(str(tmp_path / "local.db"))
    conn = _LibsqlConnection(raw)
    init_db(conn)  # type: ignore
    return conn


# ── Row compatibility (the crux) ─────────────────────────────────────────


class TestRowCompat:
    def test_dict_row_matches_sqlite_semantics(self):
        row = _LibsqlRow(("a", "b"), (1, 2))
        # dict() builds {col: value} via .keys() — exactly like sqlite3.Row
        assert dict(row) == {"a": 1, "b": 2}

    def test_iter_yields_values_like_sqlite_row(self):
        row = _LibsqlRow(("a", "b"), (1, 2))
        assert list(row) == [1, 2]

    def test_index_and_name_access(self):
        row = _LibsqlRow(("name", "score"), ("Smith", 4.5))
        assert row[0] == "Smith"
        assert row["name"] == "Smith"
        assert row[1] == 4.5
        assert row["score"] == 4.5

    def test_keys_and_contains(self):
        row = _LibsqlRow(("name", "score"), ("Smith", 4.5))
        assert row.keys() == ["name", "score"]
        assert "name" in row
        assert "missing" not in row

    def test_parity_with_real_sqlite3_row(self):
        c = sqlite3.connect(":memory:")
        c.row_factory = sqlite3.Row
        c.execute("CREATE TABLE t (a, b)")
        c.execute("INSERT INTO t VALUES (1, 2)")
        sq_row = c.execute("SELECT * FROM t").fetchone()
        my_row = _LibsqlRow(("a", "b"), (1, 2))
        assert dict(sq_row) == dict(my_row)
        assert list(sq_row) == list(my_row)
        assert sq_row["a"] == my_row["a"]


# ── End-to-end against real schema + helpers ─────────────────────────────


class TestWrapperWithAppCode:
    def test_init_db_runs_on_libsql(self, turso_conn):
        # init_db uses executescript + CREATE INDEX — should not raise
        names = {
            r["name"]
            for r in turso_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "professor_ratings" in names
        assert "time_schedule" in names

    def test_executemany_then_lookup(self, turso_conn):
        now = datetime.now(timezone.utc).isoformat()
        turso_conn.executemany(
            """INSERT INTO professor_ratings (
                 name, name_normalized, school_id, school_name, department,
                 avg_rating, avg_difficulty, num_ratings,
                 would_take_again_pct, rmp_legacy_id, last_scraped
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    "Munehiro Fukuda",
                    "MUNEHIRO FUKUDA",
                    "1431",
                    "UWB",
                    "CSS",
                    4.5,
                    3.2,
                    42,
                    88.0,
                    "987654",
                    now,
                )
            ],
        )
        turso_conn.commit()

        out = lookup_ratings(turso_conn, ["Fukuda, Munehiro"])
        assert out["Fukuda, Munehiro"]["avg_rating"] == 4.5
        assert out["Fukuda, Munehiro"]["num_ratings"] == 42
        assert out["Fukuda, Munehiro"]["rmp_url"].endswith("/987654")

    def test_fetchone_returns_none_when_empty(self, turso_conn):
        row = turso_conn.execute(
            "SELECT * FROM professor_ratings WHERE id = -1"
        ).fetchone()
        assert row is None

    def test_rollback_discards(self, turso_conn):
        now = datetime.now(timezone.utc).isoformat()
        turso_conn.execute(
            """INSERT INTO professor_ratings
               (name, name_normalized, last_scraped)
               VALUES ('X', 'X', ?)""",
            (now,),
        )
        turso_conn.rollback()
        n = turso_conn.execute("SELECT COUNT(*) FROM professor_ratings").fetchone()[0]
        assert n == 0


# ── Backend selection ────────────────────────────────────────────────────


class TestBackendSelection:
    def test_local_by_default(self, monkeypatch):
        monkeypatch.delenv("CAPSTONE_TURSO_URL", raising=False)
        monkeypatch.delenv("CAPSTONE_TURSO_AUTH_TOKEN", raising=False)
        assert using_turso() is False

    def test_turso_when_both_env_set(self, monkeypatch):
        monkeypatch.setenv("CAPSTONE_TURSO_URL", "libsql://demo.turso.io")
        monkeypatch.setenv("CAPSTONE_TURSO_AUTH_TOKEN", "tok123")
        assert using_turso() is True

    def test_local_when_only_url_set(self, monkeypatch):
        monkeypatch.setenv("CAPSTONE_TURSO_URL", "libsql://demo.turso.io")
        monkeypatch.delenv("CAPSTONE_TURSO_AUTH_TOKEN", raising=False)
        assert using_turso() is False
