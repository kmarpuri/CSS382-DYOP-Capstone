"""Program requirement scrapers — the full UW Bothell registry.

The :data:`PROGRAM_SCRAPERS` registry is the **single source of truth**
for which UW Bothell undergraduate majors this app supports. It tracks
the official UWB catalog list of 35 bachelor's degree programs.

Adding a new major is a two-step change:

1. Drop a new ``programs/<major>.py`` file that subclasses
   :class:`capstone.scrapers.base.ProgramScraper` (or
   :class:`capstone.scrapers.programs._ias_base.IASProgramScraper` for
   most IAS B.A.s) and declares ``major_code``, ``major_name``,
   ``synergies``, and ``scrape_requirements``.
2. Add it to :data:`PROGRAM_SCRAPERS` below.

The CLI's ``capstone scrape refresh`` iterates over this registry, so
no other module needs touching.
"""

# ── STEM / Computing ───────────────────────────────────────────────────
from capstone.scrapers.programs.applied_computing import AppliedComputingProgramScraper
from capstone.scrapers.programs.biology import BiologyProgramScraper
from capstone.scrapers.programs.chemistry import (
    ChemistryBAProgramScraper,
    ChemistryBSBiochemProgramScraper,
    ChemistryBSProgramScraper,
)
from capstone.scrapers.programs.computer_engineering import (
    ComputerEngineeringProgramScraper,
)
from capstone.scrapers.programs.conservation import ConservationProgramScraper
from capstone.scrapers.programs.csse import CSSEProgramScraper
from capstone.scrapers.programs.cybersecurity import (
    CybersecurityEngineeringProgramScraper,
)
from capstone.scrapers.programs.data_visualization import (
    DataVisualizationBAProgramScraper,
    DataVisualizationBSProgramScraper,
)
from capstone.scrapers.programs.electrical_engineering import (
    ElectricalEngineeringProgramScraper,
)
from capstone.scrapers.programs.env_and_earth import (
    EarthSystemScienceProgramScraper,
    EnvironmentalStudiesProgramScraper,
)
from capstone.scrapers.programs.math import MathProgramScraper
from capstone.scrapers.programs.mechanical_engineering import (
    MechanicalEngineeringProgramScraper,
)
from capstone.scrapers.programs.physics import PhysicsProgramScraper
from capstone.scrapers.programs.physics_ba import PhysicsBAProgramScraper

# ── Business ───────────────────────────────────────────────────────────
from capstone.scrapers.programs.business import BusinessAdminProgramScraper
from capstone.scrapers.programs.economics import EconomicsProgramScraper

# ── Education ──────────────────────────────────────────────────────────
from capstone.scrapers.programs.educational_extras import (
    DevelopmentalYouthStudiesProgramScraper,
    ElementaryEducationProgramScraper,
)
from capstone.scrapers.programs.educational_studies import (
    EducationalStudiesProgramScraper,
)

# ── Health & Nursing ───────────────────────────────────────────────────
from capstone.scrapers.programs.health_studies import HealthStudiesProgramScraper
from capstone.scrapers.programs.nursing import NursingProgramScraper

# ── IAS — Arts, Humanities, Social Sciences ────────────────────────────
from capstone.scrapers.programs.ias_majors import (
    AmericanEthnicStudiesProgramScraper,
    CultureLitArtsProgramScraper,
    GWSSProgramScraper,
    GlobalStudiesProgramScraper,
    InterdisciplinaryArtsProgramScraper,
    InterdisciplinarySocialSciencesProgramScraper,
    LawEconPolicyProgramScraper,
    MediaCommunicationProgramScraper,
    PsychologyProgramScraper,
    ScienceTechSocietyProgramScraper,
)

# ── Fallback for unrecognised majors ───────────────────────────────────
from capstone.scrapers.programs.stub import StubProgramScraper


# UW Bothell's authoritative undergraduate program list (35 majors).
# Order roughly mirrors the schools / catalog page.
PROGRAM_SCRAPERS: dict[str, type] = {
    # ── Computing & Engineering (STEM) ──────────────────────────
    "CSSE": CSSEProgramScraper,  # Computer Science & Software Engineering (B.S.)
    "CSSEC": CybersecurityEngineeringProgramScraper,  # CSSE (B.S. — Info Assurance & Cybersec option)
    "ACMPT": AppliedComputingProgramScraper,  # Applied Computing (B.A.)
    "CE": ComputerEngineeringProgramScraper,  # Computer Engineering (B.S.)
    "EE": ElectricalEngineeringProgramScraper,  # Electrical Engineering (B.S.)
    "ME": MechanicalEngineeringProgramScraper,  # Mechanical Engineering (B.S.)
    # ── Math & Physical Sciences (STEM) ─────────────────────────
    "MATH": MathProgramScraper,  # Mathematics (B.S.)
    "PHYS": PhysicsProgramScraper,  # Physics (B.S.)
    "PHYSBA": PhysicsBAProgramScraper,  # Physics (B.A.)
    "CHEM": ChemistryBSProgramScraper,  # Chemistry (B.S.)
    "CHEMBIO": ChemistryBSBiochemProgramScraper,  # Chemistry (B.S. — Biochem option)
    "CHEMBA": ChemistryBAProgramScraper,  # Chemistry (B.A.)
    # ── Life & Earth Sciences ───────────────────────────────────
    "BIO": BiologyProgramScraper,  # Biology (B.S.)
    "EARTH": EarthSystemScienceProgramScraper,  # Earth System Science (B.S.)
    "CRSCI": ConservationProgramScraper,  # Conservation & Restoration Science (B.S.)
    "ENVSTUD": EnvironmentalStudiesProgramScraper,  # Environmental Studies (B.A.)
    # ── Data Visualization (IAS, two variants) ──────────────────
    "DVBS": DataVisualizationBSProgramScraper,  # Data Visualization (B.S.)
    "DVBA": DataVisualizationBAProgramScraper,  # Data Visualization (B.A.)
    # ── Business ────────────────────────────────────────────────
    "BUSADM": BusinessAdminProgramScraper,  # Business Administration (B.A.)
    "ECON": EconomicsProgramScraper,  # Economics (B.S.)
    # ── Health & Nursing ────────────────────────────────────────
    "HS": HealthStudiesProgramScraper,  # Health Studies (B.A.)
    "NURS": NursingProgramScraper,  # Nursing (B.S.) — RN to BSN
    # ── Education ───────────────────────────────────────────────
    "EDUC": EducationalStudiesProgramScraper,  # Educational Studies (B.A.)
    "DYS": DevelopmentalYouthStudiesProgramScraper,  # Developmental & Youth Studies (B.A.)
    "ELEMED": ElementaryEducationProgramScraper,  # Elementary Education Option (B.A.)
    # ── IAS — Arts, Humanities, Social Sciences ─────────────────
    "AES": AmericanEthnicStudiesProgramScraper,  # American & Ethnic Studies (B.A.)
    "CLA": CultureLitArtsProgramScraper,  # Culture, Literature & the Arts (B.A.)
    "INTART": InterdisciplinaryArtsProgramScraper,  # Interdisciplinary Arts (B.A.)
    "ISS": InterdisciplinarySocialSciencesProgramScraper,  # Interdisciplinary Social Sciences (B.A.)
    "GWSS": GWSSProgramScraper,  # Gender, Women & Sexuality Studies (B.A.)
    "GLOB": GlobalStudiesProgramScraper,  # Global Studies (B.A.)
    "LEPP": LawEconPolicyProgramScraper,  # Law, Economics & Public Policy (B.A.)
    "MEDCOM": MediaCommunicationProgramScraper,  # Media & Communication Studies (B.A.)
    "PSYC": PsychologyProgramScraper,  # Psychology (B.A.)
    "STS": ScienceTechSocietyProgramScraper,  # Science, Technology & Society (B.A.)
}


def get_program_scraper(major: str):
    """Return the appropriate program scraper for the given major.

    Falls back to a :class:`StubProgramScraper` (which raises a clear
    error from ``scrape_requirements``) for unrecognised majors.
    """
    scraper_class = PROGRAM_SCRAPERS.get(major.upper())
    if scraper_class is None:
        return StubProgramScraper(major)
    return scraper_class()


def implemented_majors() -> list[dict[str, str]]:
    """Return ``[{code, name}, ...]`` for the UI dropdown, in registry order."""
    return [
        {"code": cls.major_code, "name": cls.major_name}
        for cls in PROGRAM_SCRAPERS.values()
    ]
