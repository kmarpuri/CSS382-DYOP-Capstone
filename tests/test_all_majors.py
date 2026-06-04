"""Registry-wide invariants for every implemented UW Bothell major.

This is parametrized over PROGRAM_SCRAPERS so adding a new major
*automatically* extends test coverage. If you add a major to the
registry and any of these tests start failing, fix the major file —
the contract is documented in :mod:`capstone.scrapers.base`.
"""

from __future__ import annotations

import pytest

from capstone.db.connection import connect
from capstone.db.schema import init_db
from capstone.scrapers.programs import PROGRAM_SCRAPERS


# ── Parametrize over every registered major ──────────────────────


MAJOR_IDS = sorted(PROGRAM_SCRAPERS.keys())


@pytest.fixture
def fresh_db(tmp_path):
    conn = connect(tmp_path / "majors.db")
    init_db(conn)
    yield conn
    conn.close()


@pytest.mark.parametrize("major", MAJOR_IDS)
class TestMajorContract:
    """Each registered major must satisfy these basic invariants."""

    def test_class_attributes(self, major):
        cls = PROGRAM_SCRAPERS[major]
        scraper = cls()
        assert (
            scraper.major_code == major
        ), f"{cls.__name__}.major_code must match registry key {major!r}"
        assert (
            scraper.major_name
        ), f"{cls.__name__}.major_name must be a non-empty string"
        # Synergies are optional but must be the right shape if provided
        for entry in scraper.synergies:
            assert (
                len(entry) == 3
            ), f"{major}: each synergy is (downstream, [up..], rationale)"
            downstream, upstreams, rationale = entry
            assert isinstance(downstream, str), f"{major}: downstream must be a str"
            assert isinstance(upstreams, list), f"{major}: upstreams must be a list"
            assert all(isinstance(u, str) for u in upstreams)
            assert (
                isinstance(rationale, str) and rationale
            ), f"{major}: every synergy needs a rationale string"

    def test_scrape_requirements_runs(self, major, fresh_db):
        """``scrape_requirements`` must run end-to-end without raising
        and must insert at least one row into ``major_requirements``."""
        cls = PROGRAM_SCRAPERS[major]
        n = cls().scrape_requirements(fresh_db)
        assert n > 0, f"{major}: scrape_requirements should insert > 0 rows"

        rows = fresh_db.execute(
            "SELECT COUNT(*) FROM major_requirements WHERE major = ?",
            (major,),
        ).fetchone()[0]
        assert rows > 0, f"{major}: no major_requirements rows persisted"

    def test_idempotent(self, major, fresh_db):
        """Running ``scrape_requirements`` twice should leave the same
        number of rows — the helper clears its own rows on each call."""
        cls = PROGRAM_SCRAPERS[major]
        n1 = cls().scrape_requirements(fresh_db)
        n2 = cls().scrape_requirements(fresh_db)
        assert n1 == n2, f"{major}: not idempotent ({n1} → {n2})"

    def test_records_metadata(self, major, fresh_db):
        """The scrape must stamp the scrape_metadata table so cache
        staleness can be detected by the UI."""
        cls = PROGRAM_SCRAPERS[major]
        cls().scrape_requirements(fresh_db)
        row = fresh_db.execute(
            "SELECT scraped_at, record_count FROM scrape_metadata " "WHERE source = ?",
            (f"requirements:{major}",),
        ).fetchone()
        assert row is not None, f"{major}: scrape_metadata not stamped"
        assert row[1] > 0, f"{major}: record_count not set"


# ── Registry-wide invariants ─────────────────────────────────────


class TestRegistryInvariants:
    def test_codes_are_unique(self):
        codes = [cls.major_code for cls in PROGRAM_SCRAPERS.values()]
        assert len(codes) == len(set(codes)), "duplicate major_code in registry"

    def test_names_are_unique(self):
        names = [cls.major_name for cls in PROGRAM_SCRAPERS.values()]
        assert len(names) == len(set(names)), "duplicate major_name in registry"

    def test_registry_key_matches_class_attr(self):
        for key, cls in PROGRAM_SCRAPERS.items():
            assert cls.major_code == key, (
                f"PROGRAM_SCRAPERS[{key!r}] points to {cls.__name__} "
                f"whose major_code is {cls.major_code!r}"
            )

    def test_coverage_size(self):
        """We should have a substantial registry of majors. If this
        drops below 20 by accident, something got deleted."""
        assert (
            len(PROGRAM_SCRAPERS) >= 20
        ), f"Only {len(PROGRAM_SCRAPERS)} majors registered — did one get removed?"

    def test_implemented_majors_helper(self):
        from capstone.scrapers.programs import implemented_majors

        data = implemented_majors()
        assert len(data) == len(PROGRAM_SCRAPERS)
        for entry in data:
            assert "code" in entry and "name" in entry
