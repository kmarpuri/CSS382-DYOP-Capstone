"""Pydantic models for the parsed transcript.

Output is a Transcript model — never a raw dict — so downstream consumers
get type checking and validation.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Quarter = Literal["WIN", "SPR", "SUM", "AUT"]


class PlacementTest(BaseModel):
    """A placement test result (e.g., MTHDSP 500)."""

    test_type: str
    score: str
    date: str | None = None


class TransferCredit(BaseModel):
    """A transfer / AP / IB credit, often without a true UW course mapping."""

    course_id: str
    title: str
    credits: float
    source: str = "IB"     # "IB", "AP", "TRANSFER", "RUNNING_START"
    date_range: str | None = None


class CompletedCourse(BaseModel):
    """A completed UW course with a recorded grade."""

    course_id: str         # normalized "CSS 142"
    title: str
    credits: float
    grade: str             # numeric "3.8", or "CR"/"NC"/"W"/"S" etc.
    quarter: Quarter
    year: int

    @property
    def is_passed(self) -> bool:
        """Per UW: numeric grade ≥ 0.7 (or CR/S) is a pass.

        For prerequisite satisfaction we additionally require ≥ 2.0
        — callers should use ``meets_prereq_grade`` for that check.
        """
        if self.grade in ("CR", "S", "P"):
            return True
        try:
            return float(self.grade) >= 0.7
        except ValueError:
            return False

    @property
    def is_withdrawn(self) -> bool:
        return self.grade.upper() == "W"

    def meets_prereq_grade(self, min_grade: str | None) -> bool:
        """Return True if this course's grade meets the prereq's minimum."""
        if min_grade is None:
            min_grade = "2.0"      # UW default for major prereqs
        if self.grade in ("CR", "S", "P"):
            return True
        try:
            return float(self.grade) >= float(min_grade)
        except ValueError:
            return False


class InProgressCourse(BaseModel):
    """A course the student is currently enrolled in (no grade yet)."""

    course_id: str
    title: str
    credits: float
    quarter: Quarter
    year: int


class Transcript(BaseModel):
    """Structured representation of a parsed UW transcript PDF."""

    student_name: str | None = None
    student_id: str | None = None
    campus: str = "Bothell"
    major: str | None = None            # e.g., "CSSE"
    class_standing: str | None = None   # e.g., "JUNIOR"
    current_quarter: str | None = None  # e.g., "SPRING QUARTER, 2026"

    completed: list[CompletedCourse] = Field(default_factory=list)
    in_progress: list[InProgressCourse] = Field(default_factory=list)
    transfer_credits: list[TransferCredit] = Field(default_factory=list)
    placement_tests: list[PlacementTest] = Field(default_factory=list)

    cumulative_gpa: float | None = None
    total_credits_earned: float | None = None
    uw_credits_earned: float | None = None

    parse_warnings: list[str] = Field(default_factory=list)
