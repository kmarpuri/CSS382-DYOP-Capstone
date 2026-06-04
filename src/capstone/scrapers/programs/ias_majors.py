"""IAS-school B.A. programs at UW Bothell.

Each major below subclasses :class:`IASProgramScraper` and just
declares its identity-courses. The insertion machinery, capstone
wiring, and metadata stamping all live in the base class.

The IAS school is thematic rather than sequential — the "soft prereq"
notion that drives the CSSE / engineering scrapers is less applicable
here. We still declare a small number of synergies where one course
clearly preps another, but most IAS sequencing is left to the LLM's
multi-quarter reasoning over the elective bucket.

This module covers the 11 IAS B.A. programs on UWB's official list.
Other IAS-touching majors (Environmental Studies, Conservation &
Restoration, Earth System Science, Data Visualization) live in their
own files because they have STEM-flavored prereq sequences.
"""

from __future__ import annotations

from capstone.scrapers.programs._ias_base import IASProgramScraper


class AmericanEthnicStudiesProgramScraper(IASProgramScraper):
    major_code = "AES"
    major_name = "American & Ethnic Studies (B.A.)"
    CORE = ["BIS 244", "BIS 313", "BIS 340", "BIS 405"]
    synergies = [
        (
            "BIS 405",
            ["BIS 313"],
            "Race-and-policy theory courses presume the historical groundwork in BIS 313.",
        ),
    ]


class CultureLitArtsProgramScraper(IASProgramScraper):
    major_code = "CLA"
    major_name = "Culture, Literature & the Arts (B.A.)"
    INQUIRY = ["BIS 242"]  # Humanities inquiry
    CORE = ["BIS 300", "BIS 321", "BIS 342", "BIS 410"]


class GWSSProgramScraper(IASProgramScraper):
    major_code = "GWSS"
    major_name = "Gender, Women & Sexuality Studies (B.A.)"
    CORE = ["BIS 280", "BIS 318", "BIS 380", "BIS 480"]
    synergies = [
        (
            "BIS 480",
            ["BIS 380"],
            "The senior seminar leans on the methodological tools introduced in 380.",
        ),
    ]


class GlobalStudiesProgramScraper(IASProgramScraper):
    major_code = "GLOB"
    major_name = "Global Studies (B.A.)"
    CORE = [
        "BIS 220",  # Intro to Global Studies
        "BIS 300",  # Interdisciplinary Inquiry
        "BIS 350",  # Globalization
        "BIS 365",  # Global Health
        "BIS 410",  # Global Politics
    ]
    synergies = [
        (
            "BIS 410",
            ["BIS 350"],
            "Global Politics presumes the globalization framework from BIS 350.",
        ),
    ]


class InterdisciplinaryArtsProgramScraper(IASProgramScraper):
    major_code = "INTART"
    major_name = "Interdisciplinary Arts (B.A.)"
    INQUIRY = ["BIS 242"]  # Humanities inquiry
    CORE = ["BIS 261", "BIS 305", "BIS 312", "BIS 491"]
    ELECTIVE_CREDITS = 30


class InterdisciplinarySocialSciencesProgramScraper(IASProgramScraper):
    major_code = "ISS"
    major_name = "Interdisciplinary Social Sciences (B.A.)"
    CORE = [
        "BIS 240",  # Social Science Inquiry
        "BIS 300",  # Interdisciplinary Inquiry
        "BIS 312",  # Social Theory
        "BIS 320",  # Research Design
        "BIS 422",  # Research Methods
    ]
    synergies = [
        (
            "BIS 422",
            ["BIS 320"],
            "Research Methods extends the research-design vocabulary from BIS 320.",
        ),
    ]


class LawEconPolicyProgramScraper(IASProgramScraper):
    major_code = "LEPP"
    major_name = "Law, Economics & Public Policy (B.A.)"
    CORE = [
        "BIS 220",  # Intro to Global Studies / Pol Sci
        "BIS 312",  # Constitutional Law
        "BIS 350",  # Public Policy Analysis
        "BIS 415",  # Microeconomics for Policy
        "BIS 470",  # Law & Society
    ]
    synergies = [
        (
            "BIS 415",
            ["B BUS 215"],
            "Microeconomics for policy expects basic statistical literacy.",
        ),
        (
            "BIS 470",
            ["BIS 312"],
            "Law & Society applies the constitutional framework from 312.",
        ),
    ]


class MediaCommunicationProgramScraper(IASProgramScraper):
    major_code = "MEDCOM"
    major_name = "Media & Communication Studies (B.A.)"
    CORE = [
        "BIS 232",  # Intro to Media Studies
        "BIS 333",  # Media Theory
        "BIS 348",  # Media & Society
        "BIS 412",  # Digital Media
        "BIS 440",  # Media Production
    ]
    synergies = [
        (
            "BIS 333",
            ["BIS 232"],
            "Media Theory builds on the vocabulary and history from the intro.",
        ),
        (
            "BIS 440",
            ["BIS 412"],
            "Production presumes basic comfort with digital-media tools.",
        ),
    ]


class PsychologyProgramScraper(IASProgramScraper):
    """General Psychology B.A. — the IAS social-science track, distinct
    from clinical/counseling programs at other schools."""

    major_code = "PSYC"
    major_name = "Psychology (B.A.)"
    CORE = [
        "BIS 245",  # Intro to Psychology
        "BIS 312",  # Social Psychology
        "BIS 345",  # Cognitive Psychology
        "BIS 360",  # Developmental Psychology
        "BIS 422",  # Research Methods
        "BIS 425",  # Statistics in Psychology
    ]
    synergies = [
        (
            "BIS 422",
            ["BIS 312"],
            "Research Methods uses social-psych worked examples throughout.",
        ),
        (
            "BIS 425",
            ["BIS 422"],
            "Statistics in Psych is most useful right after Research Methods.",
        ),
        (
            "BIS 360",
            ["BIS 245"],
            "Developmental Psych builds directly on intro-psych vocabulary.",
        ),
    ]


class ScienceTechSocietyProgramScraper(IASProgramScraper):
    major_code = "STS"
    major_name = "Science, Technology & Society (B.A.)"
    CORE = [
        "BIS 234",  # Intro to STS
        "BIS 300",  # Interdisciplinary Inquiry
        "BIS 342",  # Science, Technology & Society
        "BIS 412",  # Technology & Culture
        "BIS 450",  # STS Senior Seminar
    ]
    synergies = [
        (
            "BIS 412",
            ["BIS 234"],
            "Technology & Culture leans on the STS framework introduced in 234.",
        ),
        (
            "BIS 450",
            ["BIS 342"],
            "The senior seminar is the synthesis of the STS upper-division core.",
        ),
    ]
