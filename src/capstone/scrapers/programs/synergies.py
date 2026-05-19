"""Major-agnostic dispatcher for pedagogical synergies.

The synergy data itself lives on each :class:`ProgramScraper` subclass
(e.g., ``CSSEProgramScraper.synergies``). This module exposes two
public helpers that don't care which major is being processed:

* :func:`seed_synergies` — given an SQLite connection and a major code,
  ask the registered scraper for that major to persist its soft edges.
* :func:`synergy_map` — return ``{downstream: [(upstream, rationale)]}``
  for the LLM reasoner's prompt block.

If a major isn't implemented (or has no synergies defined), both
helpers no-op cleanly.
"""

from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)


def _scraper_for(major: str):
    """Return a fresh scraper instance for ``major``, or None if unknown."""
    from capstone.scrapers.programs import PROGRAM_SCRAPERS

    cls = PROGRAM_SCRAPERS.get(major.upper())
    if cls is None:
        return None
    return cls()


def seed_synergies(conn: sqlite3.Connection, major: str) -> int:
    """Persist this major's soft-prereq edges. Returns count inserted."""
    scraper = _scraper_for(major)
    if scraper is None:
        logger.debug(f"No registered scraper for major {major!r}; skipping synergies")
        return 0
    inserted = scraper.seed_synergies(conn)
    logger.info(f"Seeded {inserted} synergy edges for {major}")
    return inserted


def synergy_map(major: str) -> dict[str, list[tuple[str, str]]]:
    """Return ``{downstream: [(upstream, rationale), ...]}`` for ``major``.

    Returns an empty dict for unknown or unimplemented majors so callers
    can blindly request synergies without special-casing.
    """
    scraper = _scraper_for(major)
    if scraper is None:
        return {}
    return scraper.synergy_map()
