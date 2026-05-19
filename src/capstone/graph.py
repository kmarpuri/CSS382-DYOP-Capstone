"""Prerequisite DAG construction and traversal.

Loads ``prerequisites`` rows from SQLite into a :class:`networkx.DiGraph`,
detects cycles (which indicate scraping errors), and exposes utilities
for downstream-impact ("how many courses does this unlock?") and
prerequisite-satisfaction checks.

The DAG can be persisted to a ``.gpickle`` keyed on the catalog's
``scraped_at`` timestamp so app startup avoids re-querying SQLite.
"""

from __future__ import annotations

import logging
import pickle
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import networkx as nx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PrereqEdge:
    """A single prerequisite edge in the DAG."""

    prereq_id: str
    course_id: str
    type: str          # "required", "concurrent", "recommended", "one_of"
    group_id: int      # OR-clauses share a group_id
    min_grade: str | None


class PrereqGraph:
    """Wrapper around a ``networkx.DiGraph`` of course prerequisites.

    Edges point **from prereq → course** so the out-degree of a course
    is the number of downstream courses it unlocks.

    Each edge carries ``type``, ``group_id`` (for OR-clauses), and
    ``min_grade`` attributes copied from the SQLite prerequisites table.
    """

    def __init__(self, graph: nx.DiGraph | None = None):
        self.graph: nx.DiGraph = graph if graph is not None else nx.DiGraph()

    # ── Construction ─────────────────────────────────────────────────────

    @classmethod
    def from_db(cls, conn: sqlite3.Connection) -> "PrereqGraph":
        """Build the DAG from the ``prerequisites`` table."""
        g = nx.DiGraph()

        # All courses become nodes (even those with no prereqs)
        course_rows = conn.execute(
            "SELECT course_id, title, credits, department, offering_pattern "
            "FROM courses"
        ).fetchall()
        for row in course_rows:
            g.add_node(
                row["course_id"],
                title=row["title"],
                credits=row["credits"],
                department=row["department"],
                offering_pattern=row["offering_pattern"],
            )

        # Edges from prereq → course
        prereq_rows = conn.execute(
            "SELECT course_id, prereq_id, type, group_id, min_grade "
            "FROM prerequisites"
        ).fetchall()

        for row in prereq_rows:
            # Some prereqs reference courses that aren't in the Bothell
            # catalog (e.g., MATH 124 instead of STMATH 124). Add them as
            # placeholder nodes so the graph stays connected.
            if row["prereq_id"] not in g:
                g.add_node(row["prereq_id"], placeholder=True)
            if row["course_id"] not in g:
                continue   # course not in catalog — skip
            g.add_edge(
                row["prereq_id"],
                row["course_id"],
                type=row["type"],
                group_id=row["group_id"] or 0,
                min_grade=row["min_grade"],
            )

        gh = cls(g)
        gh._validate()
        return gh

    def _validate(self) -> None:
        """Warn (don't raise) on cycles — they indicate a scraping error."""
        if not nx.is_directed_acyclic_graph(self.graph):
            cycles = list(nx.simple_cycles(self.graph))
            logger.warning(
                f"Prerequisite graph contains {len(cycles)} cycle(s). "
                f"First cycle: {cycles[0] if cycles else None}"
            )

    # ── Persistence ──────────────────────────────────────────────────────

    def save(self, path: Path) -> None:
        """Persist the graph to a pickled file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self.graph, f)

    @classmethod
    def load(cls, path: Path) -> "PrereqGraph":
        with open(path, "rb") as f:
            return cls(pickle.load(f))

    # ── Queries ──────────────────────────────────────────────────────────

    def has(self, course_id: str) -> bool:
        return course_id in self.graph

    def downstream(self, course_id: str) -> set[str]:
        """Return all courses reachable from ``course_id`` in the DAG."""
        if course_id not in self.graph:
            return set()
        return set(nx.descendants(self.graph, course_id))

    def direct_prereqs(self, course_id: str) -> list[PrereqEdge]:
        """Return the immediate prerequisites of ``course_id``."""
        if course_id not in self.graph:
            return []
        edges = []
        for prereq_id, _, data in self.graph.in_edges(course_id, data=True):
            edges.append(
                PrereqEdge(
                    prereq_id=prereq_id,
                    course_id=course_id,
                    type=data.get("type", "required"),
                    group_id=data.get("group_id", 0),
                    min_grade=data.get("min_grade"),
                )
            )
        return edges

    def out_degree(self, course_id: str) -> int:
        """How many courses does this course directly unlock?"""
        if course_id not in self.graph:
            return 0
        return self.graph.out_degree(course_id)

    def downstream_count(self, course_id: str) -> int:
        """Transitive count of courses unlocked by this course."""
        return len(self.downstream(course_id))

    # ── Prereq satisfaction ──────────────────────────────────────────────

    def prereqs_satisfied(
        self,
        course_id: str,
        completed_grades: dict[str, str],
        *,
        allow_concurrent: bool = True,
    ) -> tuple[bool, list[str]]:
        """Check whether all prerequisites for a course are satisfied.

        ``completed_grades`` maps ``course_id → grade``. Grades may be
        numeric strings ("3.2"), "CR"/"S"/"P", or "W"/"I"/"N"/"NC".

        OR-clauses (group_id > 0) are satisfied if at least one option
        in the group is satisfied.

        Returns ``(ok, reasons)`` where ``reasons`` lists any unmet
        prerequisite(s).
        """
        edges = self.direct_prereqs(course_id)
        if not edges:
            return True, []

        # Group by group_id. group_id == 0 means independent (AND-clauses).
        by_group: dict[int, list[PrereqEdge]] = defaultdict(list)
        for e in edges:
            by_group[e.group_id].append(e)

        reasons: list[str] = []

        # Independent prereqs (group_id 0): each must be satisfied
        for e in by_group.get(0, []):
            if e.type == "recommended":
                continue
            if e.type == "concurrent":
                # Lenient mode: a concurrent prereq doesn't have to be
                # already completed — it can be taken in the same quarter.
                if allow_concurrent:
                    continue
                if not _grade_meets(completed_grades.get(e.prereq_id), e.min_grade):
                    reasons.append(f"missing concurrent prereq {e.prereq_id}")
                continue
            if not _grade_meets(completed_grades.get(e.prereq_id), e.min_grade):
                reasons.append(
                    f"missing prereq {e.prereq_id}"
                    + (f" (min grade {e.min_grade})" if e.min_grade else "")
                )

        # OR groups: any one option must satisfy
        for gid, options in by_group.items():
            if gid == 0:
                continue
            if any(_grade_meets(completed_grades.get(opt.prereq_id), opt.min_grade)
                   for opt in options):
                continue
            opt_names = " or ".join(o.prereq_id for o in options)
            reasons.append(f"missing one_of {{{opt_names}}}")

        return len(reasons) == 0, reasons


# ── Helpers ──────────────────────────────────────────────────────────────

def _grade_meets(grade: str | None, min_grade: str | None) -> bool:
    """Return True if ``grade`` satisfies ``min_grade`` (default 2.0 per UW)."""
    if grade is None:
        return False
    if grade.upper() in ("W", "I", "N", "NC", "IP", ""):
        return False
    if grade in ("CR", "S", "P"):
        return True
    try:
        g = float(grade)
        m = float(min_grade) if min_grade else 2.0
        return g >= m
    except (ValueError, TypeError):
        return False
