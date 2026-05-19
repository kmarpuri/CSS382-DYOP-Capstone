"""Program requirement scrapers sub-package."""

from capstone.scrapers.programs.csse import CSSEProgramScraper
from capstone.scrapers.programs.stub import StubProgramScraper

# Registry of implemented program scrapers
PROGRAM_SCRAPERS: dict[str, type] = {
    "CSSE": CSSEProgramScraper,
}


def get_program_scraper(major: str):
    """Return the appropriate program scraper for the given major.

    Raises NotImplementedError for unimplemented majors.
    """
    scraper_class = PROGRAM_SCRAPERS.get(major.upper())
    if scraper_class is None:
        return StubProgramScraper(major)
    return scraper_class()
