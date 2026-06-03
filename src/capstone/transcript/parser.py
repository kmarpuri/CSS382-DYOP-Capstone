"""Transcript PDF parser.

Pipeline:
1. ``pdfplumber`` extracts text (primary).
2. ``pypdf`` falls back if pdfplumber fails or returns empty text.
3. ``pytesseract`` OCR is the last resort for scanned transcripts
   (imported lazily — Tesseract is an optional system dependency).

The parser is text-pattern-based — it doesn't rely on PDF coordinates.
That is robust against minor layout drift between UW transcript versions.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from capstone.transcript.models import (
    CompletedCourse,
    InProgressCourse,
    PlacementTest,
    Quarter,
    Transcript,
    TransferCredit,
)

logger = logging.getLogger(__name__)


# ── Quarter normalization ───────────────────────────────────────────────────

QUARTER_MAP: dict[str, Quarter] = {
    "WINTER": "WIN",
    "SPRING": "SPR",
    "SUMMER": "SUM",
    "AUTUMN": "AUT",
    "FALL": "AUT",
}


def _normalize_quarter(name: str) -> Quarter:
    """Normalize a full quarter name (e.g., 'AUTUMN') to its 3-letter code."""
    up = name.upper().strip()
    if up not in QUARTER_MAP:
        raise ValueError(f"Unknown quarter name: {name!r}")
    return QUARTER_MAP[up]


# ── Course-code normalization ───────────────────────────────────────────────

# UW course codes can have multi-word prefixes ("B WRIT 134", "B BUS 215",
# "CSSSKL 142"). On the transcript these are emitted with variable column
# widths, so we collapse all internal whitespace to a single space.
def _normalize_course_id(raw: str) -> str:
    return re.sub(r"\s+", " ", raw.strip())


# ── PDF text extraction ─────────────────────────────────────────────────────

def _extract_text_pdfplumber(path: Path) -> str:
    """Extract text from a UW transcript PDF, splitting two-column layouts.

    UW unofficial transcripts use a two-column layout for the per-quarter
    records. ``page.extract_text()`` joins left-column and right-column
    text on the same line, corrupting course data. We instead crop each
    page into left and right halves and read them in reading order.

    The header (name, ID, major) is single-column at the top, so we
    extract it from a full-width strip first.
    """
    try:
        import pdfplumber
    except ImportError as e:
        raise RuntimeError("pdfplumber is required for transcript parsing") from e

    parts: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            w, h = page.width, page.height
            # Heuristic: top 12% of the page is single-column header.
            header_top = 0
            header_bottom = h * 0.15
            split_x = w / 2 + 5    # nudge the split slightly right of center

            try:
                header_text = page.crop((0, header_top, w, header_bottom)).extract_text() or ""
                left_text = page.crop((0, header_bottom, split_x, h)).extract_text() or ""
                right_text = page.crop((split_x, header_bottom, w, h)).extract_text() or ""
            except Exception:
                # If cropping fails, fall back to whole-page extraction.
                header_text = ""
                left_text = page.extract_text() or ""
                right_text = ""

            parts.append(header_text)
            parts.append(left_text)
            parts.append(right_text)

    return "\n".join(parts)


def _extract_text_pypdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""

    reader = PdfReader(str(path))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def _extract_text_ocr(path: Path) -> str:    # pragma: no cover - optional dep
    try:
        import pdf2image
        import pytesseract
    except ImportError:
        return ""

    images = pdf2image.convert_from_path(str(path))
    return "\n".join(pytesseract.image_to_string(im) for im in images)


def extract_transcript_text(path: Path) -> str:
    """Extract text from a transcript PDF, trying multiple backends.

    Returns the first non-empty text extraction.
    """
    extractors = [
        ("pdfplumber", _extract_text_pdfplumber),
        ("pypdf", _extract_text_pypdf),
        ("ocr", _extract_text_ocr),
    ]
    for name, fn in extractors:
        try:
            text = fn(path)
        except Exception as e:
            logger.warning(f"{name} extraction failed: {e}")
            continue
        if text and text.strip():
            logger.debug(f"Extracted transcript text using {name}")
            return text
    raise RuntimeError(f"All PDF extractors failed for {path}")


# ── Parser ──────────────────────────────────────────────────────────────────

# Course prefix: 1-2 letters/letters-with-space-letters, optionally followed
# by an all-caps token. Matches "CSS", "STMATH", "B WRIT", "B CORE", "BEARTH".
COURSE_PREFIX = r"(?:[A-Z]{1,2}\s+)?[A-Z][A-Z]+"
COURSE_NUM = r"\d{3}"

# A completed-course line on the UW transcript:
#   "CSS    142 CMPT PROG I             5.0  3.8"
#   "CSSSKL 142 CMPT PROG SKILLS I      1.0  CR"
#   "B WRIT 134 COMPOSITION             5.0  4.0"
# Credits is a decimal, grade is decimal / CR / NC / W / S / I / IP / N.
COMPLETED_LINE = re.compile(
    rf"^\s*({COURSE_PREFIX})\s+({COURSE_NUM})\s+(.+?)\s+(\d+\.\d)\s+(\d\.\d|CR|NC|W|S|I|IP|N|HW|HP)\s*$",
)

# An in-progress-course line (no grade, but with credits):
#   "CSS    382 INTRO TO AI             5.0"
INPROGRESS_LINE = re.compile(
    rf"^\s*({COURSE_PREFIX})\s+({COURSE_NUM})\s+(.+?)\s+(\d+\.\d)\s*$",
)

# A quarter-header line:
#   "AUTUMN 2024  B PRE 1"
#   "WINTER 2026  CSSE 3"
QUARTER_HEADER = re.compile(
    r"^\s*(WINTER|SPRING|SUMMER|AUTUMN|FALL)\s+(\d{4})\b",
    re.IGNORECASE,
)

# Cumulative-GPA line at the end:
#   "UW GRADE POINT AVG.  3.63 CREDITS EARNED  107.0"
CUM_GPA_LINE = re.compile(
    r"UW GRADE POINT AVG[.\s]+(\d+\.\d{1,2}).*?CREDITS EARNED\s+(\d+\.\d)",
    re.IGNORECASE | re.DOTALL,
)

# Single placement-test line:
#   "FYCDSP 01 07/31/24"
PLACEMENT_LINE = re.compile(
    r"^\s*([A-Z]{3,8})\s+(\d{1,4})\s+(\d{2}/\d{2}/\d{2,4})\s*$",
)

# IB / AP credit block: an indented "PREFIX NUM TITLE CREDITS" then
#   "(date range)" on the following line.
IB_CREDIT_LINE = re.compile(
    rf"^\s*({COURSE_PREFIX})\s+({COURSE_NUM})\s+(.+?)\s+(\d+\.\d)\s*$",
)


class TranscriptParser:
    """Parse the text of a UW transcript into a :class:`Transcript`."""

    def __init__(self, debug: bool = False):
        self.debug = debug

    # ── Public entry point ────────────────────────────────────────────────

    def parse(self, path: Path) -> Transcript:
        text = extract_transcript_text(path)
        return self.parse_text(text)

    def parse_text(self, text: str) -> Transcript:
        transcript = Transcript()
        lines = text.splitlines()

        self._parse_header(lines, transcript)
        self._parse_transfer_credits(lines, transcript)
        self._parse_quarters(lines, transcript)
        self._parse_in_progress(lines, transcript)
        self._parse_summary(text, transcript)
        self._parse_placement_tests(lines, transcript)

        return transcript

    # ── Header (name, ID, major, standing) ────────────────────────────────

    def _parse_header(self, lines: list[str], t: Transcript) -> None:
        for i, line in enumerate(lines[:40]):
            up = line.upper()

            # Major from the campus/program header line:
            #   "Krish Marpuri   UW Bothell  COMP SCI & SOFTWARE ENGR"
            if "COMP SCI & SOFTWARE ENGR" in up:
                t.major = "CSSE"
            elif "MATHEMATICS" in up and ("UW Bothell" in line or "UW BOTHELL" in up):
                t.major = "MATH"

            if "UW Bothell" in line or "UW BOTHELL" in up:
                t.campus = "Bothell"
            elif "UW Seattle" in line or "UW SEATTLE" in up:
                t.campus = "Seattle"
            elif "UW Tacoma" in line or "UW TACOMA" in up:
                t.campus = "Tacoma"

            # Student name: extract everything before "UW Bothell/Seattle/Tacoma".
            if t.student_name is None:
                name_m = re.match(
                    r"^\s*([A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+){0,3})\s+UW\s+(Bothell|Seattle|Tacoma)\b",
                    line,
                )
                if name_m:
                    t.student_name = name_m.group(1).strip()

            # Student ID line — 7-8 digits at the start of a line
            id_m = re.match(r"^\s*(\d{7,8})\b", line)
            if id_m and t.student_id is None:
                t.student_id = id_m.group(1)

            # Class standing + current quarter
            for standing in ("FRESHMAN", "SOPHOMORE", "JUNIOR", "SENIOR", "GRADUATE"):
                if standing in up and "CURRENTLY ENROLLED" in up:
                    t.class_standing = standing
                    break
            cq = re.search(r"\(([A-Z]+ QUARTER,\s*\d{4})\)", up)
            if cq and t.current_quarter is None:
                t.current_quarter = cq.group(1)

    # ── AP / IB / transfer credits ────────────────────────────────────────

    def _parse_transfer_credits(self, lines: list[str], t: Transcript) -> None:
        """Parse the block under "EXTENSION/INDEPENDENT STDY/ADVANCE PLACEMENT CREDIT:"."""
        in_block = False
        current_source = "TRANSFER"

        for i, line in enumerate(lines):
            up = line.upper()
            if "EXTENSION/INDEPENDENT STDY/ADVANCE PLACEMENT CREDIT" in up:
                in_block = True
                continue

            if not in_block:
                continue

            # The block ends at the first horizontal rule or the first
            # quarter header.
            if line.strip().startswith("---") or QUARTER_HEADER.match(line):
                in_block = False
                continue

            if "INTERNATIONAL BACCALAUREATE" in up:
                current_source = "IB"
                continue
            if "ADVANCED PLACEMENT" in up or " AP " in f" {up} ":
                current_source = "AP"
                continue
            if "RUNNING START" in up:
                current_source = "RUNNING_START"
                continue
            if "TRANSFER" in up:
                current_source = "TRANSFER"
                continue

            if "TOTAL EXTENSION" in up or "TOTAL APPLIED" in up:
                continue

            m = IB_CREDIT_LINE.match(line)
            if not m:
                continue

            prefix, num, title, credits = m.groups()
            cid = _normalize_course_id(f"{prefix} {num}")
            # Look ahead for the "(date range)" line
            date_range = None
            if i + 1 < len(lines):
                dr = re.match(r"^\s*\((.+?)\)\s*$", lines[i + 1])
                if dr:
                    date_range = dr.group(1)

            t.transfer_credits.append(
                TransferCredit(
                    course_id=cid,
                    title=title.strip(),
                    credits=float(credits),
                    source=current_source,
                    date_range=date_range,
                )
            )

    # ── Per-quarter graded courses ────────────────────────────────────────

    def _parse_quarters(self, lines: list[str], t: Transcript) -> None:
        """Walk the file and emit a CompletedCourse for each graded line.

        The active quarter is set by the most-recent QUARTER_HEADER line.
        Lines after the "WORK IN PROGRESS" banner are skipped — those go to
        ``_parse_in_progress``.
        """
        current_quarter: Quarter | None = None
        current_year: int | None = None
        in_wip = False

        for line in lines:
            if "WORK IN PROGRESS" in line.upper():
                in_wip = True
                continue
            if in_wip:
                continue

            qh = QUARTER_HEADER.match(line)
            if qh:
                try:
                    current_quarter = _normalize_quarter(qh.group(1))
                    current_year = int(qh.group(2))
                except ValueError:
                    pass
                continue

            if current_quarter is None or current_year is None:
                continue

            m = COMPLETED_LINE.match(line)
            if not m:
                continue

            prefix, num, title, credits, grade = m.groups()
            # Skip placeholder lines that look like courses but are summaries
            cid = _normalize_course_id(f"{prefix} {num}")

            t.completed.append(
                CompletedCourse(
                    course_id=cid,
                    title=title.strip(),
                    credits=float(credits),
                    grade=grade,
                    quarter=current_quarter,
                    year=current_year,
                )
            )

    # ── Work-in-progress block ────────────────────────────────────────────

    def _parse_in_progress(self, lines: list[str], t: Transcript) -> None:
        in_wip = False
        current_quarter: Quarter | None = None
        current_year: int | None = None

        for line in lines:
            if "WORK IN PROGRESS" in line.upper():
                in_wip = True
                continue
            if not in_wip:
                continue
            if "END OF RECORD" in line.upper():
                break

            qh = QUARTER_HEADER.match(line)
            if qh:
                try:
                    current_quarter = _normalize_quarter(qh.group(1))
                    current_year = int(qh.group(2))
                except ValueError:
                    pass
                continue

            if current_quarter is None or current_year is None:
                continue

            # In-progress lines have credits but no grade
            # Skip the "QTR REGISTERED:" summary line
            if "QTR REGISTERED" in line.upper():
                continue
            if "Bothell CAMPUS" in line or "Seattle CAMPUS" in line:
                continue

            m = INPROGRESS_LINE.match(line)
            if not m:
                continue

            prefix, num, title, credits = m.groups()
            cid = _normalize_course_id(f"{prefix} {num}")

            t.in_progress.append(
                InProgressCourse(
                    course_id=cid,
                    title=title.strip(),
                    credits=float(credits),
                    quarter=current_quarter,
                    year=current_year,
                )
            )

    # ── Cumulative summary ────────────────────────────────────────────────

    def _parse_summary(self, text: str, t: Transcript) -> None:
        m = CUM_GPA_LINE.search(text)
        if m:
            t.cumulative_gpa = float(m.group(1))
            t.total_credits_earned = float(m.group(2))

        uw_earned = re.search(r"UW CREDITS EARNED\s+(\d+\.\d)", text)
        if uw_earned:
            t.uw_credits_earned = float(uw_earned.group(1))

    # ── Placement tests ───────────────────────────────────────────────────

    def _parse_placement_tests(self, lines: list[str], t: Transcript) -> None:
        in_block = False
        for line in lines:
            if "PLACEMENT TESTS" in line.upper():
                in_block = True
                continue
            if not in_block:
                continue
            if "EXTENSION" in line.upper() or line.strip().startswith("---"):
                in_block = False
                continue
            m = PLACEMENT_LINE.match(line)
            if m:
                t.placement_tests.append(
                    PlacementTest(
                        test_type=m.group(1),
                        score=m.group(2),
                        date=m.group(3),
                    )
                )


# ── Module-level convenience ───────────────────────────────────────────────

def parse_transcript(path: Path | str, debug: bool = False) -> Transcript:
    """Parse a transcript PDF and return a :class:`Transcript`."""
    parser = TranscriptParser(debug=debug)
    return parser.parse(Path(path))
