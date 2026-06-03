"""Phase 5 — exercise every registered ProgramScraper as a single
parametrized suite.

Spec acceptance for Phase 5:
  "No core logic changes should be needed if Phase 1's abstraction was
   clean — this phase is primarily new scraper implementations and test
   coverage per major."

These tests prove the abstraction holds:
  * Every registered scraper can populate major_requirements.
  * Every registered scraper seeds synergies via the shared base method.
  * The factory and registry agree on every code.
  * The CLI dispatch (iterating PROGRAM_SCRAPERS) covers every major.
"""

from __future__ import annotations

import pytest

from capstone.db.connection import connect
from capstone.db.schema import init_db
from capstone.scrapers.base import ProgramScraper
from capstone.scrapers.programs import (
    PROGRAM_SCRAPERS,
    get_program_scraper,
    implemented_majors,
)
from capstone.scrapers.programs.stub import StubProgramScraper


@pytest.fixture
def fresh_db(tmp_path):
    conn = connect(tmp_path / "phase5.db")
    init_db(conn)
    yield conn
    conn.close()


# Every test below is parametrized over EVERY registered major,
# so adding a new major file + registry entry automatically expands
# this suite.
ALL_MAJORS = sorted(PROGRAM_SCRAPERS.keys())


class TestRegistry:
    """Invariants of the PROGRAM_SCRAPERS registry."""

    def test_registry_non_empty(self):
        assert len(PROGRAM_SCRAPERS) >= 30, (
            "Phase 5 covers UWB's full undergraduate catalog (~35 majors). "
            "If you intentionally removed one, update this assertion."
        )

    def test_registry_matches_uwb_official_count(self):
        """UW Bothell's official undergraduate-degrees page lists 35 programs."""
        assert len(PROGRAM_SCRAPERS) == 35, (
            f"Expected 35 UWB undergraduate majors per the official list; "
            f"got {len(PROGRAM_SCRAPERS)}."
        )

    def test_includes_canonical_majors(self):
        """A handful of canonical codes that must always be present."""
        for code in ("CSSE", "BUSADM", "MATH", "BIO", "PSYC", "NURS", "HS", "ECON"):
            assert code in PROGRAM_SCRAPERS, f"{code} missing from registry"

    def test_all_majors_subclass_program_scraper(self):
        for code, cls in PROGRAM_SCRAPERS.items():
            assert issubclass(
                cls, ProgramScraper
            ), f"{code} → {cls.__name__} doesn't subclass ProgramScraper"

    def test_major_codes_match_class_attrs(self):
        """The registry key must equal the class's declared major_code."""
        for code, cls in PROGRAM_SCRAPERS.items():
            assert (
                cls.major_code == code
            ), f"Registry key {code!r} != class attribute {cls.major_code!r}"

    def test_major_names_populated(self):
        for cls in PROGRAM_SCRAPERS.values():
            assert cls.major_name, f"{cls.__name__} has no major_name"


@pytest.mark.parametrize("major", ALL_MAJORS)
class TestEveryMajor:
    """Per-major smoke tests — parametrized over the whole registry."""

    def test_scrape_requirements_succeeds(self, fresh_db, major):
        scraper = get_program_scraper(major)
        count = scraper.scrape_requirements(fresh_db)
        assert count > 0, f"{major} scraper produced no requirement rows"

    def test_capstone_row_present(self, fresh_db, major):
        scraper = get_program_scraper(major)
        scraper.scrape_requirements(fresh_db)
        row = fresh_db.execute(
            "SELECT COUNT(*) FROM major_requirements "
            "WHERE major = ? AND category = 'capstone'",
            (major,),
        ).fetchone()
        assert row[0] >= 1, f"{major} has no capstone row"

    def test_idempotent(self, fresh_db, major):
        """Running twice must not duplicate rows (uses _clear_existing_requirements)."""
        scraper = get_program_scraper(major)
        scraper.scrape_requirements(fresh_db)
        n1 = fresh_db.execute(
            "SELECT COUNT(*) FROM major_requirements WHERE major = ?",
            (major,),
        ).fetchone()[0]

        scraper.scrape_requirements(fresh_db)
        n2 = fresh_db.execute(
            "SELECT COUNT(*) FROM major_requirements WHERE major = ?",
            (major,),
        ).fetchone()[0]
        assert n1 == n2, f"{major} doubled to {n2} rows on second run"

    def test_synergies_well_formed(self, fresh_db, major):
        """If a major declares synergies, every entry is a 3-tuple of the
        right shape and references real-looking course IDs."""
        scraper = get_program_scraper(major)
        import re

        for entry in scraper.synergies:
            assert len(entry) == 3, f"{major}: malformed synergy tuple {entry!r}"
            downstream, upstreams, rationale = entry
            assert isinstance(downstream, str) and downstream.strip()
            assert isinstance(upstreams, list) and upstreams
            assert all(
                re.match(r"^[A-Z][A-Z ]{0,8}\s+\d{3}$", u)
                for u in [downstream] + upstreams
            ), f"{major}: invalid course-ID format in {entry!r}"
            assert isinstance(rationale, str) and len(rationale) > 10

    def test_synergy_map_dispatcher(self, major):
        """The major-agnostic synergy dispatcher must return this major's
        data when given its code."""
        from capstone.scrapers.programs.synergies import synergy_map

        scraper = get_program_scraper(major)
        dispatched = synergy_map(major)
        direct = scraper.synergy_map()
        assert (
            dispatched == direct
        ), f"{major}: dispatcher returned different data than the class method"


class TestFactoryDispatch:
    """get_program_scraper should resolve every registered code correctly."""

    @pytest.mark.parametrize("major", ALL_MAJORS)
    def test_factory_returns_concrete_scraper(self, major):
        scraper = get_program_scraper(major)
        assert not isinstance(scraper, StubProgramScraper)
        assert scraper.major_code == major

    def test_factory_returns_stub_for_unknown(self):
        scraper = get_program_scraper("NOT_A_REAL_MAJOR")
        assert isinstance(scraper, StubProgramScraper)

    def test_factory_case_insensitive(self):
        s1 = get_program_scraper("csse")
        s2 = get_program_scraper("CSSE")
        assert type(s1) is type(s2)


class TestImplementedMajorsHelper:
    """The UI hits implemented_majors() to populate its dropdown."""

    def test_returns_list_of_dicts(self):
        majors = implemented_majors()
        assert isinstance(majors, list)
        for m in majors:
            assert set(m.keys()) == {"code", "name"}

    def test_covers_full_registry(self):
        majors = implemented_majors()
        codes = {m["code"] for m in majors}
        assert codes == set(PROGRAM_SCRAPERS.keys())
