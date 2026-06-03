"""Tests for the transcript parser.

These exercise the text-based parser directly (without a PDF) so the
suite has no dependency on pdfplumber rendering. The integration test
parses the bundled real transcript if it's present.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from capstone.transcript.models import CompletedCourse
from capstone.transcript.parser import TranscriptParser


# ── Synthesized transcript text fixtures ───────────────────────────────

SAMPLE_CSSE_TEXT = """\
UNIVERSITY OF WASHINGTON Page 1 of 1
UNOFFICIAL ACADEMIC TRANSCRIPT
Prepared on 5/18/2026
Krish Marpuri UW Bothell COMP SCI & SOFTWARE ENGR
2429082 01/23/XX
JUNIOR CURRENTLY ENROLLED (SPRING QUARTER, 2026)
PLACEMENT TESTS: TYPE SCORE DATE
FYCDSP 01 07/31/24
MTHDSP 500 05/06/24
EXTENSION/INDEPENDENT STDY/ADVANCE PLACEMENT CREDIT:
INTERNATIONAL BACCALAUREATE:
CHEM 142 IB CHEMISTRY 5.0
(05/01/24-07/08/24)
MATH 120 IB MATH ANALY APPR 5.0
(05/01/24-07/08/24)
TOTAL EXTENSION/CORRESPONDENCE/AP CREDIT: 10.0
----
AUTUMN 2024 B PRE 1
Bothell CAMPUS
CSS 142 CMPT PROG I 5.0 3.8
STMATH 124 CALCULUS I 5.0 4.0
WINTER 2025 B PRE 2
Bothell CAMPUS
CSS 143 CMPT PROG II 5.0 3.0
STMATH 125 CALCULUS II 5.0 3.9
B WRIT 134 COMPOSITION 5.0 4.0
SPRING 2025 B PRE 2
Bothell CAMPUS
CSS 240 WITHDRAWN COURSE 5.0 W
CSSSKL 143 CMPT PROG SKILLS II 1.0 CR
CUMULATIVE CREDIT SUMMARY:
UW CREDITS ATTEMPTED 21.0 UW CREDITS EARNED 21.0
UW GRADE POINT AVG. 3.55 CREDITS EARNED 31.0
***************** WORK IN PROGRESS *****************
SPRING 2026 CSSE 3
Bothell CAMPUS
CSS 382 INTRO TO AI 5.0
STMATH 224 MULTIVAR CALCULUS 5.0
QTR REGISTERED: 10.0
****************** END OF RECORD *******************
"""


SAMPLE_NO_AP_TEXT = """\
Jane Doe UW Bothell MATHEMATICS
1234567 02/02/XX
SOPHOMORE CURRENTLY ENROLLED (AUTUMN QUARTER, 2025)
AUTUMN 2024 B PRE 1
Bothell CAMPUS
STMATH 124 CALCULUS I 5.0 3.2
CUMULATIVE CREDIT SUMMARY:
UW GRADE POINT AVG. 3.20 CREDITS EARNED 5.0
"""


# ── Tests ────────────────────────────────────────────────────────────────


class TestHeaderParsing:
    def test_extracts_student_basics(self):
        t = TranscriptParser().parse_text(SAMPLE_CSSE_TEXT)
        assert t.student_name == "Krish Marpuri"
        assert t.student_id == "2429082"
        assert t.major == "CSSE"
        assert t.campus == "Bothell"
        assert t.class_standing == "JUNIOR"
        assert t.current_quarter == "SPRING QUARTER, 2026"

    def test_handles_minimal_header(self):
        t = TranscriptParser().parse_text(SAMPLE_NO_AP_TEXT)
        assert t.student_name == "Jane Doe"
        assert t.class_standing == "SOPHOMORE"


class TestCompletedCourses:
    def test_extracts_graded_courses(self):
        t = TranscriptParser().parse_text(SAMPLE_CSSE_TEXT)
        cids = {c.course_id for c in t.completed}
        assert "CSS 142" in cids
        assert "CSS 143" in cids
        assert "STMATH 124" in cids
        assert "B WRIT 134" in cids
        assert "CSSSKL 143" in cids

    def test_course_attributes(self):
        t = TranscriptParser().parse_text(SAMPLE_CSSE_TEXT)
        by_id = {c.course_id: c for c in t.completed}

        css142 = by_id["CSS 142"]
        assert css142.credits == 5.0
        assert css142.grade == "3.8"
        assert css142.quarter == "AUT"
        assert css142.year == 2024

        css_skl = by_id["CSSSKL 143"]
        assert css_skl.grade == "CR"
        assert css_skl.is_passed

    def test_withdrawn_flagged(self):
        t = TranscriptParser().parse_text(SAMPLE_CSSE_TEXT)
        css240 = next(c for c in t.completed if c.course_id == "CSS 240")
        assert css240.is_withdrawn
        assert not css240.is_passed


class TestInProgress:
    def test_extracts_wip_courses(self):
        t = TranscriptParser().parse_text(SAMPLE_CSSE_TEXT)
        wip = {c.course_id for c in t.in_progress}
        assert wip == {"CSS 382", "STMATH 224"}

    def test_wip_does_not_appear_in_completed(self):
        t = TranscriptParser().parse_text(SAMPLE_CSSE_TEXT)
        completed_ids = {c.course_id for c in t.completed}
        assert "CSS 382" not in completed_ids
        assert "STMATH 224" not in completed_ids


class TestTransferCredits:
    def test_ib_credits(self):
        t = TranscriptParser().parse_text(SAMPLE_CSSE_TEXT)
        assert any(
            tc.course_id == "CHEM 142" and tc.source == "IB"
            for tc in t.transfer_credits
        )
        assert any(
            tc.course_id == "MATH 120" and tc.source == "IB"
            for tc in t.transfer_credits
        )


class TestSummary:
    def test_gpa_and_credits(self):
        t = TranscriptParser().parse_text(SAMPLE_CSSE_TEXT)
        assert t.cumulative_gpa == 3.55
        assert t.total_credits_earned == 31.0
        assert t.uw_credits_earned == 21.0


class TestPlacementTests:
    def test_extracts_placement(self):
        t = TranscriptParser().parse_text(SAMPLE_CSSE_TEXT)
        types = {p.test_type for p in t.placement_tests}
        assert types == {"FYCDSP", "MTHDSP"}


class TestGradePolicy:
    """CompletedCourse exposes UW grade semantics."""

    def test_meets_prereq_grade(self):
        c = CompletedCourse(
            course_id="CSS 142",
            title="x",
            credits=5.0,
            grade="2.0",
            quarter="AUT",
            year=2024,
        )
        assert c.meets_prereq_grade(None)  # default 2.0
        assert c.meets_prereq_grade("2.0")
        assert not c.meets_prereq_grade("2.5")

    def test_cr_satisfies_anything(self):
        c = CompletedCourse(
            course_id="X",
            title="x",
            credits=1.0,
            grade="CR",
            quarter="AUT",
            year=2024,
        )
        assert c.meets_prereq_grade("2.8")

    def test_withdrawn_never_passes(self):
        c = CompletedCourse(
            course_id="X",
            title="x",
            credits=5.0,
            grade="W",
            quarter="AUT",
            year=2024,
        )
        assert not c.is_passed


# ── Integration: parse the real fixture PDF if available ─────────────────

FIXTURE_PDF = Path(__file__).parent.parent / "UWUnofficialTranscript.pdf"


@pytest.mark.skipif(not FIXTURE_PDF.exists(), reason="fixture PDF not present")
class TestRealPDFFixture:
    def test_real_transcript_parses(self):
        from capstone.transcript import parse_transcript

        t = parse_transcript(FIXTURE_PDF)
        assert t.student_name
        assert t.major == "CSSE"
        assert len(t.completed) >= 15
        # The bundled transcript has CSS 343 completed
        assert any(c.course_id == "CSS 343" for c in t.completed)
