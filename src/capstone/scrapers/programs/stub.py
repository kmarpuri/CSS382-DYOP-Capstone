"""Stub program scraper for unimplemented majors.

Raises a clear error directing users to Phase 5, where additional
major scrapers will be implemented.
"""

from __future__ import annotations

import sqlite3

from capstone.scrapers.base import ProgramScraper


class StubProgramScraper(ProgramScraper):
    """Placeholder scraper for majors not yet implemented."""

    def __init__(self, major: str):
        self.major_code = major.upper()
        self.major_name = f"{major} (not yet implemented)"

    def scrape_requirements(self, conn: sqlite3.Connection) -> int:
        """Raise NotImplementedError with a helpful message."""
        raise NotImplementedError(
            f"Program scraper for '{self.major_code}' is not yet implemented. "
            f"Currently, only CSSE is supported. "
            f"Additional majors will be added in Phase 5. "
            f"To contribute a new major scraper, subclass ProgramScraper "
            f"and register it in capstone/scrapers/programs/__init__.py."
        )
