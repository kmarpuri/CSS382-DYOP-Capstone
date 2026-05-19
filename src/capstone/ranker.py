"""Deterministic course ranker.

Computes per-course scores from four independent signals:

* ``criticality_score`` — out-degree in the prereq DAG, weighted by
  whether downstream courses are required for the student's major.
* ``availability_score`` — inverse of offering frequency. Rare courses
  rank higher because deferring them costs more.
* ``progress_score`` — how directly the course advances unmet major
  requirements.
* ``balance_penalty`` — applied per plan (not per course) to penalize
  too many high-difficulty courses stacked in one quarter.

Weights are loaded from ``config.yaml`` so tuning doesn't require code
changes.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass, field

from capstone.config import AppConfig
from capstone.graph import PrereqGraph
from capstone.transcript.models import Transcript

logger = logging.getLogger(__name__)


# ── Per-course scoring output ─────────────────────────────────────────────

@dataclass
class CourseScore:
    """A single course's deterministic scoring breakdown."""

    course_id: str
    title: str
    credits: float
    criticality_score: float = 0.0
    availability_score: float = 0.0
    progress_score: float = 0.0
    synergy_score: float = 0.0       # soft-prereq prep completeness
    raw_difficulty: float = 0.0      # used for balance penalty later
    eligibility_ok: bool = True
    eligibility_reasons: list[str] = field(default_factory=list)
    offered_next_quarter: bool = True
    fits_major: bool = True
    offering_pattern: str | None = None
    reasoning: str | None = None

    @property
    def combined_score(self) -> float:
        """Not used directly — Ranker applies the weighted combination."""
        return (
            0.4 * self.criticality_score
            + 0.3 * self.progress_score
            + 0.3 * self.availability_score
        )


# ── Eligibility / completion bookkeeping ──────────────────────────────────

def build_completed_grades(transcript: Transcript) -> dict[str, str]:
    """Map ``course_id → best grade`` across the transcript.

    Handles repeats by keeping the highest numeric grade (matches UW's
    repeat policy where the higher grade is used for prereq evaluation).
    Includes transfer/AP/IB credits as ``"S"`` (satisfactory) so they
    can satisfy prereqs.
    """
    best: dict[str, str] = {}

    for c in transcript.completed:
        if c.is_withdrawn:
            continue
        existing = best.get(c.course_id)
        if existing is None:
            best[c.course_id] = c.grade
            continue

        def _num(g: str) -> float:
            try:
                return float(g)
            except ValueError:
                return -1.0 if g.upper() != "CR" else 0.0

        if _num(c.grade) > _num(existing):
            best[c.course_id] = c.grade

    for tc in transcript.transfer_credits:
        # Transfer credits count as Satisfactory but only if not already
        # taken at UW.
        if tc.course_id not in best:
            best[tc.course_id] = "S"

    # In-progress courses count toward prereq satisfaction *concurrently*.
    # We add them to a sibling map; satisfaction tests can opt in/out.
    return best


def build_in_progress_set(transcript: Transcript) -> set[str]:
    return {c.course_id for c in transcript.in_progress}


# ── Ranker ────────────────────────────────────────────────────────────────

# Offering-pattern letter → quarter (UW notation: A=Aut, W=Win, Sp=Spr, S=Sum)
_OFFERING_PATTERN_RE = re.compile(r"A|W|Sp|S")
QUARTER_LETTER = {"AUT": "A", "WIN": "W", "SPR": "Sp", "SUM": "S"}
NUMERIC_QUARTER_TO_LETTER = {"AUT": "A", "WIN": "W", "SPR": "Sp", "SUM": "S"}


def _parse_offering_letters(pattern: str | None) -> set[str]:
    """Parse an 'AWSpS' offering pattern into {'A','W','Sp','S'}."""
    if not pattern:
        return set()
    # Strip "Offered: jointly with X;" prefixes
    pattern = re.sub(r"jointly with [^;.]+;\s*", "", pattern, flags=re.IGNORECASE)
    out: set[str] = set()
    i = 0
    while i < len(pattern):
        if pattern[i:i + 2] == "Sp":
            out.add("Sp")
            i += 2
        elif pattern[i] in ("A", "W", "S"):
            out.add(pattern[i])
            i += 1
        else:
            i += 1
    return out


def _is_offered_in(quarter_code: str | None, offering_pattern: str | None) -> bool:
    """Best-effort: would this course be offered in the given quarter?

    If no offering pattern is known, default to True (don't filter out)
    rather than silently drop candidates.
    """
    if quarter_code is None or offering_pattern is None:
        return True
    target_letter = NUMERIC_QUARTER_TO_LETTER.get(quarter_code.upper())
    if target_letter is None:
        return True
    letters = _parse_offering_letters(offering_pattern)
    if not letters:
        return True
    return target_letter in letters


def _offering_frequency(offering_pattern: str | None) -> int:
    """Number of quarters per year this course is offered. 0–4."""
    return len(_parse_offering_letters(offering_pattern))


# ── Major-requirement loading ────────────────────────────────────────────

def load_major_requirements(
    conn: sqlite3.Connection, major: str
) -> list[dict]:
    """Return rows from major_requirements as plain dicts."""
    rows = conn.execute(
        "SELECT category, course_id, required_count, group_id, notes "
        "FROM major_requirements WHERE major = ?",
        (major,),
    ).fetchall()
    return [dict(r) for r in rows]


def unmet_requirements(
    requirements: list[dict],
    completed: dict[str, str],
    in_progress: set[str],
) -> list[dict]:
    """Filter requirements to those not yet satisfied."""
    have = set(completed.keys()) | in_progress
    unmet: list[dict] = []
    # Group OR-clauses: if any member of the group is satisfied, drop all
    by_group: dict[tuple[str, int], list[dict]] = {}
    standalone: list[dict] = []
    for r in requirements:
        gid = r.get("group_id", 0)
        if gid and gid > 0:
            by_group.setdefault((r["category"], gid), []).append(r)
        else:
            standalone.append(r)

    for r in standalone:
        cid = r["course_id"]
        # The "elective" marker row ("CSS 200+") is open-ended;
        # consider it unmet until we count credits, handled by caller.
        if cid.endswith("+") or "elective" == r["category"]:
            unmet.append(r)
            continue
        if cid not in have:
            unmet.append(r)

    for (cat, gid), options in by_group.items():
        if any(o["course_id"] in have for o in options):
            continue
        unmet.extend(options)

    return unmet


# ── The main ranker class ────────────────────────────────────────────────

class Ranker:
    """Score every eligible course in the catalog for the next quarter."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        config: AppConfig,
        graph: PrereqGraph | None = None,
    ):
        self.conn = conn
        self.config = config
        self.graph = graph or PrereqGraph.from_db(conn)

    # ── Public entry point ─────────────────────────────────────────────

    def score_all(
        self,
        transcript: Transcript,
        target_quarter: str | None = None,
    ) -> list[CourseScore]:
        """Return CourseScore for every catalog course, eligible or not.

        Caller can filter by ``eligibility_ok`` to drop unreachables.

        ``target_quarter`` is a 3-letter code: 'AUT', 'WIN', 'SPR', 'SUM'.
        """
        if target_quarter:
            target_quarter = target_quarter.upper()[:3]

        completed = build_completed_grades(transcript)
        in_progress = build_in_progress_set(transcript)

        # Load concrete time-schedule offerings for the target quarter.
        # If the time schedule has entries for the target quarter, we
        # treat *only* those as offered; otherwise we fall back to the
        # catalog's offering_pattern.
        scheduled_for_target: set[str] = set()
        if target_quarter:
            ts_rows = self.conn.execute(
                "SELECT DISTINCT course_id FROM time_schedule WHERE quarter = ?",
                (target_quarter,),
            ).fetchall()
            scheduled_for_target = {r["course_id"] for r in ts_rows}

        # Major-aware downstream weighting
        major_requirements = (
            load_major_requirements(self.conn, transcript.major)
            if transcript.major
            else []
        )
        unmet = unmet_requirements(major_requirements, completed, in_progress)
        unmet_course_ids = {r["course_id"] for r in unmet}

        # Identify courses the student is *already* eligible for. Those are
        # not part of any candidate's "effective downstream" — they don't
        # need to be unlocked.
        already_eligible: set[str] = set()
        for node in self.graph.graph.nodes:
            if node in completed and _passes(completed[node]):
                already_eligible.add(node)
                continue
            if node in in_progress:
                already_eligible.add(node)
                continue
            ok, _ = self.graph.prereqs_satisfied(
                node, completed_grades=completed, allow_concurrent=True
            )
            if ok:
                already_eligible.add(node)

        # Precompute "actually unlocked" sets per candidate course. A course
        # c "unlocks" d only if d is currently ineligible AND taking c
        # *would* make d's prereqs satisfied (considering OR-clauses with
        # the student's existing courses).
        effective_by_course: dict[str, set[str]] = {}
        for cid in self.graph.graph.nodes:
            if cid in already_eligible and cid not in completed and cid not in in_progress:
                # Course is eligible for the student but not yet taken;
                # downstream might still be ineligible.
                pass
            unlocked = set()
            pseudo = dict(completed)
            pseudo[cid] = pseudo.get(cid) or "S"
            for d in self.graph.downstream(cid):
                if d in already_eligible:
                    continue
                ok_with, _ = self.graph.prereqs_satisfied(
                    d, completed_grades=pseudo, allow_concurrent=True
                )
                if ok_with:
                    unlocked.add(d)
            effective_by_course[cid] = unlocked

        all_eff_counts = [len(s) for s in effective_by_course.values()]
        max_downstream = max(all_eff_counts) if all_eff_counts else 1
        if max_downstream == 0:
            max_downstream = 1

        scores: list[CourseScore] = []
        course_rows = self.conn.execute(
            "SELECT course_id, title, credits, offering_pattern, description, department "
            "FROM courses"
        ).fetchall()

        for row in course_rows:
            cid = row["course_id"]

            # Skip courses already passed or in progress
            if cid in completed and _passes(completed[cid]):
                continue
            if cid in in_progress:
                continue
            # Skip graduate-level courses (500+) for undergraduate planning
            if _course_level(cid) >= 500:
                continue

            score = CourseScore(
                course_id=cid,
                title=row["title"] or "",
                credits=_parse_credits(row["credits"]),
                offering_pattern=row["offering_pattern"],
            )

            # Prereq eligibility — concurrent prereqs may be in progress
            allow_concurrent = True
            ok, reasons = self.graph.prereqs_satisfied(
                cid,
                completed_grades=completed,
                allow_concurrent=allow_concurrent,
            )
            # Concurrent prereqs may be satisfied by in-progress courses
            if not ok and in_progress:
                # Retry treating in-progress as completed for concurrent edges
                combined = dict(completed)
                for ip in in_progress:
                    combined.setdefault(ip, "IP")
                ok2, reasons2 = self.graph.prereqs_satisfied(
                    cid, completed_grades=combined, allow_concurrent=True
                )
                # Only allow the re-pass if the failing edges were concurrent
                # We approximate this by accepting ok2 over ok.
                if ok2:
                    ok, reasons = True, []

            score.eligibility_ok = ok
            score.eligibility_reasons = reasons

            # Offered next quarter?
            if scheduled_for_target:
                score.offered_next_quarter = cid in scheduled_for_target
            else:
                score.offered_next_quarter = _is_offered_in(
                    target_quarter, row["offering_pattern"]
                )

            # Criticality: count downstream courses that this candidate
            # *would actually unlock* (i.e., become eligible because of this
            # course, considering OR-clauses). Bonus when the unlocked set
            # includes unmet major requirements.
            effective = effective_by_course.get(cid, set())
            base_crit = len(effective) / max_downstream
            major_relevance = 1.0
            if unmet_course_ids and effective:
                overlap = effective & unmet_course_ids
                major_relevance = 1.0 + 0.5 * (len(overlap) / max(1, len(effective)))
            score.criticality_score = min(1.0, base_crit * major_relevance)

            # Availability: rarer = higher
            freq = _offering_frequency(row["offering_pattern"])
            if freq == 0:
                # unknown — treat as average (offered 2x/yr)
                score.availability_score = 0.5
            else:
                score.availability_score = round((4 - freq + 1) / 4.0, 3)

            # Progress: 1.0 if this course directly satisfies an unmet req,
            # smaller fraction if it's a *necessary* prereq for an unmet req
            # (one whose other paths the student hasn't taken).
            if cid in unmet_course_ids:
                score.progress_score = 1.0
                score.fits_major = True
            else:
                effective_unmet = effective & unmet_course_ids
                if effective_unmet:
                    score.progress_score = min(0.8, 0.3 + 0.15 * len(effective_unmet))
                    score.fits_major = True
                else:
                    score.progress_score = 0.0
                    score.fits_major = False

            # Synergy: count completed "recommended"-type prereqs. Captures
            # the "you've already done the prep that makes this easier"
            # pedagogical signal (e.g., CSS 422 → CSS 430).
            soft_edges = [
                e for e in self.graph.direct_prereqs(cid)
                if e.type == "recommended"
            ]
            if soft_edges:
                completed_soft = sum(
                    1 for e in soft_edges
                    if e.prereq_id in completed
                    and _passes(completed[e.prereq_id])
                )
                score.synergy_score = completed_soft / len(soft_edges)
            else:
                score.synergy_score = 0.0

            # Raw difficulty proxy: 0–1 normalized course level (300+ harder)
            level = _course_level(cid)
            score.raw_difficulty = min(1.0, max(0.0, (level - 100) / 400.0))

            scores.append(score)

        return scores

    # ── Combined ranking ──────────────────────────────────────────────────

    def rank(self, scores: list[CourseScore]) -> list[CourseScore]:
        """Sort scores in descending order of the configured weighted combo.

        The balance penalty is applied at the plan level, not here — so we
        ignore it for per-course ordering.
        """
        w = self.config.ranking_weights
        return sorted(
            scores,
            key=lambda s: (
                w.criticality * s.criticality_score
                + w.availability * s.availability_score
                + w.progress * s.progress_score
                + w.synergy * s.synergy_score
            ),
            reverse=True,
        )


# ── helpers ──────────────────────────────────────────────────────────────

def _passes(grade: str) -> bool:
    if grade in ("CR", "S", "P"):
        return True
    try:
        return float(grade) >= 0.7
    except ValueError:
        return False


def _parse_credits(raw: str | None) -> float:
    """Best-effort: turn '5', '1-5', '(1-5, max. 6)' into a float."""
    if not raw:
        return 0.0
    # If a range like "1-5", use the upper bound
    m = re.match(r"\s*(\d+)\s*[-–]\s*(\d+)", raw)
    if m:
        return float(m.group(2))
    m = re.match(r"\s*(\d+(?:\.\d+)?)", raw)
    if m:
        return float(m.group(1))
    return 0.0


def _course_level(course_id: str) -> int:
    """Return the 100/200/.../500 numeric level of the course."""
    m = re.search(r"(\d{3})", course_id)
    if not m:
        return 100
    return (int(m.group(1)) // 100) * 100
