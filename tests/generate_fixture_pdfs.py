"""Generate synthesized UW Unofficial Transcript PDFs for testing.

Uses ``reportlab`` to emit PDFs that match the layout of real UW transcripts:
two-column per-quarter records, a single-column header, placement tests, AP/IB
transfer credits, work-in-progress blocks, and cumulative summary lines.

Each generator function returns a ``Path`` to the written PDF. Tests call these
via the ``fixture_pdfs`` pytest fixture (see conftest.py) so files are created
in ``tmp_path`` and cleaned up automatically.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

# Text must fit within the left-column crop of the parser's two-column
# extractor (~50% of page width). Use a small font + tight x-offset.
_FONT = "Courier"
_FONT_SIZE = 8
_X = 0.5 * inch
_LINE = 12  # line spacing in points


# ── Helpers ────────────────────────────────────────────────────────────────

def _draw_header(c: canvas.Canvas, name: str, sid: str, campus: str,
                 major_label: str, standing: str, quarter_label: str,
                 y: float) -> float:
    """Draw the transcript header block and return the new Y position.

    The parser's regex expects:
      - name + "UW Bothell" + major_label ALL on one line
      - standing + "CURRENTLY ENROLLED" + "(QUARTER)" on one line
    We use a tiny font for long lines so they fit in the left-column crop.
    """
    c.setFont(_FONT, _FONT_SIZE)
    c.drawString(_X, y, "UNIVERSITY OF WASHINGTON")
    y -= _LINE
    c.drawString(_X, y, "UNOFFICIAL ACADEMIC TRANSCRIPT")
    y -= _LINE
    c.drawString(_X, y, "Prepared on 5/18/2026")
    y -= _LINE + 4
    # Parser expects name + campus + major on ONE line
    header_line = f"{name} UW {campus} {major_label}"
    c.setFont(_FONT, 6)  # shrink to fit in left-column crop
    c.drawString(_X, y, header_line)
    y -= _LINE
    c.setFont(_FONT, _FONT_SIZE)
    c.drawString(_X, y, f"{sid} 01/23/XX")
    y -= _LINE
    # Parser expects standing + CURRENTLY ENROLLED + (QUARTER) on one line
    standing_line = f"{standing} CURRENTLY ENROLLED ({quarter_label})"
    c.setFont(_FONT, 6)
    c.drawString(_X, y, standing_line)
    y -= _LINE + 6
    c.setFont(_FONT, _FONT_SIZE)
    return y


def _draw_placement_tests(c: canvas.Canvas, tests: list[tuple[str, str, str]],
                           y: float) -> float:
    """Draw the PLACEMENT TESTS block."""
    if not tests:
        return y
    c.drawString(_X, y, "PLACEMENT TESTS:")
    y -= _LINE
    for ttype, score, date in tests:
        c.drawString(_X, y, f"{ttype} {score} {date}")
        y -= _LINE
    y -= 4
    return y


def _draw_transfer_block(c: canvas.Canvas,
                          credits: list[tuple[str, str, str, str, str, str]],
                          y: float) -> float:
    """Draw EXTENSION/INDEPENDENT STDY/ADVANCE PLACEMENT CREDIT block.

    Each credit entry: (source_label, course_id, title, credits, date_start, date_end)

    The parser's ``_parse_transfer_credits`` requires the sentinel string
    ``EXTENSION/INDEPENDENT STDY/ADVANCE PLACEMENT CREDIT`` on ONE line.
    """
    if not credits:
        return y
    # Must be on a single line — shrink font to fit in the left-column crop
    c.setFont(_FONT, 5)
    c.drawString(_X, y,
                 "EXTENSION/INDEPENDENT STDY/ADVANCE PLACEMENT CREDIT:")
    y -= _LINE
    c.setFont(_FONT, _FONT_SIZE)
    current_source = None
    for source, cid, title, cred, ds, de in credits:
        if source != current_source:
            c.drawString(_X, y, source)
            y -= _LINE
            current_source = source
        c.drawString(_X, y, f"{cid} {title} {cred}")
        y -= _LINE
        if ds and de:
            c.drawString(_X, y, f"({ds}-{de})")
            y -= _LINE
    total = sum(float(cr[3]) for cr in credits)
    c.drawString(_X, y, f"TOTAL APPLIED CREDIT: {total:.1f}")
    y -= _LINE
    c.drawString(_X, y, "----")
    y -= _LINE
    return y


def _draw_quarter(c: canvas.Canvas, quarter_name: str, year: int,
                   level_label: str, campus: str,
                   courses: list[tuple[str, str, str, str]],
                   y: float) -> float:
    """Draw a single quarter block (header + course lines).

    Each course: (course_id, title, credits, grade)
    """
    c.drawString(_X, y, f"{quarter_name} {year} {level_label}")
    y -= _LINE
    c.drawString(_X, y, f"{campus} CAMPUS")
    y -= _LINE
    for cid, title, cred, grade in courses:
        c.drawString(_X, y, f"{cid} {title} {cred} {grade}")
        y -= _LINE
    y -= 4
    return y


def _draw_wip(c: canvas.Canvas, quarter_name: str, year: int,
              level_label: str, campus: str,
              courses: list[tuple[str, str, str]],
              y: float) -> float:
    """Draw the WORK IN PROGRESS block.

    Each course: (course_id, title, credits) — no grade.
    """
    c.drawString(_X, y, "****** WORK IN PROGRESS ******")
    y -= _LINE
    c.drawString(_X, y, f"{quarter_name} {year} {level_label}")
    y -= _LINE
    c.drawString(_X, y, f"{campus} CAMPUS")
    y -= _LINE
    total = 0.0
    for cid, title, cred in courses:
        c.drawString(_X, y, f"{cid} {title} {cred}")
        y -= _LINE
        total += float(cred)
    c.drawString(_X, y, f"QTR REGISTERED: {total:.1f}")
    y -= _LINE
    c.drawString(_X, y, "******* END OF RECORD ********")
    y -= _LINE
    return y


def _draw_summary(c: canvas.Canvas, gpa: float, total_credits: float,
                   uw_credits: float, y: float) -> float:
    """Draw the CUMULATIVE CREDIT SUMMARY block."""
    c.drawString(_X, y, "CUMULATIVE CREDIT SUMMARY:")
    y -= _LINE
    c.drawString(_X, y,
                 f"UW CREDITS EARNED {uw_credits:.1f}")
    y -= _LINE
    c.drawString(_X, y,
                 f"UW GRADE POINT AVG. {gpa:.2f}")
    y -= _LINE
    c.drawString(_X, y,
                 f"CREDITS EARNED {total_credits:.1f}")
    y -= _LINE + 6
    return y


def _new_page_if_needed(c: canvas.Canvas, y: float,
                         margin: float = 1.0 * inch) -> float:
    """Start a new page if y is too low."""
    if y < margin:
        c.showPage()
        c.setFont(_FONT, _FONT_SIZE)
        y = 10.5 * inch
    return y


# ── PDF generators ────────────────────────────────────────────────────────

def generate_csse_junior(out_dir: Path) -> Path:
    """Standard CSSE junior with ~15 completed courses, IB credits, WIP."""
    path = out_dir / "csse_junior.pdf"
    c = canvas.Canvas(str(path), pagesize=letter)
    c.setFont(_FONT, _FONT_SIZE)
    y = 10.5 * inch

    y = _draw_header(c, "Krish Marpuri", "2429082", "Bothell",
                     "COMP SCI & SOFTWARE ENGR", "JUNIOR",
                     "SPRING QUARTER, 2026", y)

    y = _draw_placement_tests(c, [
        ("FYCDSP", "01", "07/31/24"),
        ("MTHDSP", "500", "05/06/24"),
    ], y)

    y = _draw_transfer_block(c, [
        ("INTERNATIONAL BACCALAUREATE",
         "CHEM 142", "IB CHEMISTRY", "5.0", "05/01/24", "07/08/24"),
        ("INTERNATIONAL BACCALAUREATE",
         "MATH 120", "IB MATH ANALY APPR", "5.0", "05/01/24", "07/08/24"),
    ], y)

    y = _draw_quarter(c, "AUTUMN", 2024, "B PRE 1", "Bothell", [
        ("CSS 142", "CMPT PROG I", "5.0", "3.8"),
        ("CSSSKL 142", "CMPT PROG SKILLS I", "1.0", "CR"),
        ("STMATH 124", "CALCULUS I", "5.0", "4.0"),
    ], y)

    y = _new_page_if_needed(c, y)

    y = _draw_quarter(c, "WINTER", 2025, "B PRE 2", "Bothell", [
        ("CSS 143", "CMPT PROG II", "5.0", "3.0"),
        ("CSSSKL 143", "CMPT PROG SKILLS II", "1.0", "CR"),
        ("STMATH 125", "CALCULUS II", "5.0", "3.9"),
        ("B WRIT 134", "COMPOSITION", "5.0", "4.0"),
    ], y)

    y = _new_page_if_needed(c, y)

    y = _draw_quarter(c, "SPRING", 2025, "B PRE 2", "Bothell", [
        ("B BUS 215", "INTRO TO BUS STATS", "5.0", "3.7"),
        ("B WRIT 135", "RESEARCH WRITING", "5.0", "4.0"),
    ], y)

    y = _new_page_if_needed(c, y)

    y = _draw_quarter(c, "AUTUMN", 2025, "CSSE 2", "Bothell", [
        ("CSS 342", "DATA, ALG, MATH I", "5.0", "3.2"),
        ("STMATH 126", "CALCULUS III", "5.0", "3.5"),
    ], y)

    y = _draw_quarter(c, "WINTER", 2026, "CSSE 3", "Bothell", [
        ("CSS 301", "W-TECHNICAL WRITING", "5.0", "3.0"),
        ("CSS 343", "DATA, ALG, MATH II", "5.0", "3.5"),
    ], y)

    y = _new_page_if_needed(c, y)

    y = _draw_summary(c, 3.55, 62.0, 52.0, y)

    y = _draw_wip(c, "SPRING", 2026, "CSSE 3", "Bothell", [
        ("CSS 382", "INTRO TO AI", "5.0"),
        ("STMATH 224", "MULTIVAR CALCULUS", "5.0"),
    ], y)

    c.save()
    return path


def generate_freshman_minimal(out_dir: Path) -> Path:
    """Freshman with only 1 quarter, no transfers, no WIP."""
    path = out_dir / "freshman_minimal.pdf"
    c = canvas.Canvas(str(path), pagesize=letter)
    c.setFont("Courier", 10)
    y = 10.5 * inch

    y = _draw_header(c, "Jane Doe", "1234567", "Bothell",
                     "COMP SCI & SOFTWARE ENGR", "FRESHMAN",
                     "WINTER QUARTER, 2025", y)

    y = _draw_quarter(c, "AUTUMN", 2024, "B PRE 1", "Bothell", [
        ("CSS 142", "CMPT PROG I", "5.0", "3.5"),
        ("STMATH 124", "CALCULUS I", "5.0", "3.8"),
        ("B WRIT 134", "COMPOSITION", "5.0", "4.0"),
    ], y)

    y = _draw_summary(c, 3.77, 15.0, 15.0, y)

    c.save()
    return path


def generate_senior_heavy(out_dir: Path) -> Path:
    """Senior with many courses, withdrawn courses, and high GPA."""
    path = out_dir / "senior_heavy.pdf"
    c = canvas.Canvas(str(path), pagesize=letter)
    c.setFont("Courier", 10)
    y = 10.5 * inch

    y = _draw_header(c, "Alex Johnson", "9876543", "Bothell",
                     "COMP SCI & SOFTWARE ENGR", "SENIOR",
                     "SPRING QUARTER, 2026", y)

    quarters = [
        ("AUTUMN", 2023, "B PRE 1", [
            ("CSS 142", "CMPT PROG I", "5.0", "4.0"),
            ("CSSSKL 142", "CMPT PROG SKILLS I", "1.0", "CR"),
            ("STMATH 124", "CALCULUS I", "5.0", "3.9"),
            ("B CORE 104", "DISC CORE: ART & HUM", "5.0", "3.7"),
        ]),
        ("WINTER", 2024, "B PRE 2", [
            ("CSS 143", "CMPT PROG II", "5.0", "3.8"),
            ("CSSSKL 143", "CMPT PROG SKILLS II", "1.0", "CR"),
            ("STMATH 125", "CALCULUS II", "5.0", "4.0"),
            ("B WRIT 134", "COMPOSITION", "5.0", "3.9"),
        ]),
        ("SPRING", 2024, "B PRE 2", [
            ("B BUS 215", "INTRO TO BUS STATS", "5.0", "3.6"),
            ("B WRIT 135", "RESEARCH WRITING", "5.0", "4.0"),
            ("CSS 240", "WEB PROGRAMMING", "5.0", "W"),
        ]),
        ("AUTUMN", 2024, "CSSE 2", [
            ("CSS 301", "W-TECHNICAL WRITING", "5.0", "3.5"),
            ("CSS 342", "DATA, ALG, MATH I", "5.0", "3.8"),
            ("STMATH 126", "CALCULUS III", "5.0", "3.7"),
        ]),
        ("WINTER", 2025, "CSSE 3", [
            ("CSS 343", "DATA, ALG, MATH II", "5.0", "3.9"),
            ("CSS 350", "MANAGEMENT PRINCIPLES", "5.0", "3.3"),
            ("STMATH 207", "INTRO TO DIFF EQ", "5.0", "4.0"),
        ]),
        ("SPRING", 2025, "CSSE 3", [
            ("CSS 360", "SOFTWARE ENGINEERING", "5.0", "3.6"),
            ("CSS 370", "ANALYSIS & DESIGN", "5.0", "3.4"),
            ("STMATH 208", "MATRIX ALGEBRA", "5.0", "3.8"),
        ]),
        ("AUTUMN", 2025, "CSSE 4", [
            ("CSS 422", "HW & COMPUTER ORG", "5.0", "3.7"),
            ("CSS 430", "OPERATING SYSTEMS", "5.0", "3.5"),
        ]),
        ("WINTER", 2026, "CSSE 4", [
            ("CSS 382", "INTRO TO AI", "5.0", "3.9"),
            ("CSS 450", "ELECTIVE COURSE", "5.0", "W"),
        ]),
    ]

    for qname, yr, label, courses in quarters:
        y = _new_page_if_needed(c, y, margin=1.5 * inch)
        y = _draw_quarter(c, qname, yr, label, "Bothell", courses, y)

    y = _new_page_if_needed(c, y)
    y = _draw_summary(c, 3.72, 146.0, 146.0, y)

    c.save()
    return path


def generate_transfer_student(out_dir: Path) -> Path:
    """Heavy AP/IB/Running Start credits."""
    path = out_dir / "transfer_student.pdf"
    c = canvas.Canvas(str(path), pagesize=letter)
    c.setFont("Courier", 10)
    y = 10.5 * inch

    y = _draw_header(c, "Maria Garcia", "5551234", "Bothell",
                     "COMP SCI & SOFTWARE ENGR", "SOPHOMORE",
                     "SPRING QUARTER, 2026", y)

    y = _draw_transfer_block(c, [
        ("INTERNATIONAL BACCALAUREATE",
         "CHEM 142", "IB CHEMISTRY", "5.0", "05/01/23", "07/08/23"),
        ("INTERNATIONAL BACCALAUREATE",
         "MATH 120", "IB MATH ANALY APPR", "5.0", "05/01/23", "07/08/23"),
        ("INTERNATIONAL BACCALAUREATE",
         "PHYS 101", "IB PHYSICS", "5.0", "05/01/23", "07/08/23"),
        ("INTERNATIONAL BACCALAUREATE",
         "PHYS 102", "IB PHYSICS", "5.0", "05/01/23", "07/08/23"),
        ("ADVANCED PLACEMENT",
         "ENGL 111", "ENGLISH LANG", "5.0", "05/01/23", "08/01/23"),
        ("ADVANCED PLACEMENT",
         "CSE 142", "COMPUTER SCI A", "5.0", "05/01/23", "08/01/23"),
        ("RUNNING START",
         "STMATH 124", "RS CALCULUS I", "5.0", "09/01/22", "12/15/22"),
        ("RUNNING START",
         "STMATH 125", "RS CALCULUS II", "5.0", "01/05/23", "03/20/23"),
    ], y)

    y = _new_page_if_needed(c, y)

    y = _draw_quarter(c, "AUTUMN", 2024, "B PRE 1", "Bothell", [
        ("CSS 142", "CMPT PROG I", "5.0", "4.0"),
        ("B CORE 104", "DISC CORE: ART & HUM", "5.0", "3.6"),
    ], y)

    y = _draw_quarter(c, "WINTER", 2025, "B PRE 2", "Bothell", [
        ("CSS 143", "CMPT PROG II", "5.0", "3.8"),
        ("B WRIT 134", "COMPOSITION", "5.0", "3.9"),
    ], y)

    y = _draw_summary(c, 3.83, 60.0, 20.0, y)

    y = _draw_wip(c, "SPRING", 2026, "CSSE 2", "Bothell", [
        ("CSS 342", "DATA, ALG, MATH I", "5.0"),
    ], y)

    c.save()
    return path


def generate_math_major(out_dir: Path) -> Path:
    """Non-CSSE major (Mathematics) to test major detection."""
    path = out_dir / "math_major.pdf"
    c = canvas.Canvas(str(path), pagesize=letter)
    c.setFont("Courier", 10)
    y = 10.5 * inch

    y = _draw_header(c, "Bob Smith", "7654321", "Bothell",
                     "MATHEMATICS", "JUNIOR",
                     "WINTER QUARTER, 2026", y)

    y = _draw_quarter(c, "AUTUMN", 2024, "B PRE 1", "Bothell", [
        ("STMATH 124", "CALCULUS I", "5.0", "3.9"),
        ("B WRIT 134", "COMPOSITION", "5.0", "3.5"),
    ], y)

    y = _draw_quarter(c, "WINTER", 2025, "B PRE 2", "Bothell", [
        ("STMATH 125", "CALCULUS II", "5.0", "4.0"),
        ("STMATH 126", "CALCULUS III", "5.0", "3.8"),
    ], y)

    y = _draw_quarter(c, "SPRING", 2025, "MATH 2", "Bothell", [
        ("STMATH 207", "INTRO TO DIFF EQ", "5.0", "3.7"),
        ("STMATH 208", "MATRIX ALGEBRA", "5.0", "4.0"),
    ], y)

    y = _draw_summary(c, 3.82, 30.0, 30.0, y)

    c.save()
    return path


def generate_edge_cases(out_dir: Path) -> Path:
    """Mixed grades (CR/NC/W/S/IP/HW/HP) and unusual course prefixes."""
    path = out_dir / "edge_cases.pdf"
    c = canvas.Canvas(str(path), pagesize=letter)
    c.setFont("Courier", 10)
    y = 10.5 * inch

    y = _draw_header(c, "Test Student", "1111111", "Bothell",
                     "COMP SCI & SOFTWARE ENGR", "SOPHOMORE",
                     "AUTUMN QUARTER, 2025", y)

    y = _draw_quarter(c, "AUTUMN", 2024, "B PRE 1", "Bothell", [
        ("CSS 142", "CMPT PROG I", "5.0", "3.8"),
        ("CSSSKL 142", "CMPT PROG SKILLS I", "1.0", "CR"),
        ("B WRIT 134", "COMPOSITION", "5.0", "S"),
        ("B CORE 104", "DISC CORE: ART & HUM", "5.0", "NC"),
    ], y)

    y = _draw_quarter(c, "WINTER", 2025, "B PRE 2", "Bothell", [
        ("CSS 143", "CMPT PROG II", "5.0", "W"),
        ("STMATH 124", "CALCULUS I", "5.0", "HW"),
        ("B BUS 215", "INTRO TO BUS STATS", "5.0", "HP"),
    ], y)

    y = _draw_quarter(c, "SPRING", 2025, "B PRE 2", "Bothell", [
        ("BEARTH 320", "CLIMATE IMPACTS", "5.0", "3.1"),
        ("CSS 143", "CMPT PROG II", "5.0", "2.5"),
        ("STMATH 124", "CALCULUS I", "5.0", "N"),
    ], y)

    y = _draw_summary(c, 2.85, 51.0, 51.0, y)

    c.save()
    return path


def generate_dense_two_column(out_dir: Path) -> Path:
    """Many courses across multiple quarters to stress extraction."""
    path = out_dir / "two_column_dense.pdf"
    c = canvas.Canvas(str(path), pagesize=letter)
    c.setFont("Courier", 10)
    y = 10.5 * inch

    y = _draw_header(c, "Dense Transcript", "9999999", "Bothell",
                     "COMP SCI & SOFTWARE ENGR", "SENIOR",
                     "SPRING QUARTER, 2026", y)

    # Generate 8 quarters with 4 courses each = 32 total
    semesters = [
        ("AUTUMN", 2022), ("WINTER", 2023), ("SPRING", 2023), ("AUTUMN", 2023),
        ("WINTER", 2024), ("SPRING", 2024), ("AUTUMN", 2024), ("WINTER", 2025),
    ]
    course_num = 100
    for qname, yr in semesters:
        courses = []
        for j in range(4):
            cn = course_num + j
            courses.append((f"CSS {cn}", f"COURSE TITLE {cn}", "5.0", "3.5"))
        course_num += 10
        y = _new_page_if_needed(c, y, margin=1.5 * inch)
        y = _draw_quarter(c, qname, yr, "CSSE", "Bothell", courses, y)

    y = _new_page_if_needed(c, y)
    y = _draw_summary(c, 3.50, 160.0, 160.0, y)

    c.save()
    return path


# ── Public API ──────────────────────────────────────────────────────────────

ALL_GENERATORS = {
    "csse_junior": generate_csse_junior,
    "freshman_minimal": generate_freshman_minimal,
    "senior_heavy": generate_senior_heavy,
    "transfer_student": generate_transfer_student,
    "math_major": generate_math_major,
    "edge_cases": generate_edge_cases,
    "two_column_dense": generate_dense_two_column,
}


def generate_all(out_dir: Path) -> dict[str, Path]:
    """Generate all fixture PDFs into ``out_dir``. Returns {name: path}."""
    out_dir.mkdir(parents=True, exist_ok=True)
    return {name: fn(out_dir) for name, fn in ALL_GENERATORS.items()}
