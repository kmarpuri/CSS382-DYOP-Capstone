"""Tests for the prerequisite DAG."""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import pytest

from capstone.graph import PrereqGraph, _grade_meets


class TestGraphConstruction:
    def test_load_from_db(self, fixture_db):
        g = PrereqGraph.from_db(fixture_db)
        assert g.has("CSS 342")
        assert g.has("CSS 497")
        # Direct prereq lookup
        prereqs = {e.prereq_id for e in g.direct_prereqs("CSS 343")}
        assert prereqs == {"CSS 342", "CSS 301"}

    def test_acyclic(self, fixture_db):
        g = PrereqGraph.from_db(fixture_db)
        assert nx.is_directed_acyclic_graph(g.graph)

    def test_downstream_traversal(self, fixture_db):
        g = PrereqGraph.from_db(fixture_db)
        # CSS 342 → CSS 343, CSS 370, CSS 422, then transitively CSS 430, CSS 497
        downstream = g.downstream("CSS 342")
        assert "CSS 343" in downstream
        assert "CSS 430" in downstream  # via CSS 343
        assert "CSS 370" in downstream
        assert "CSS 422" in downstream

    def test_pickle_roundtrip(self, fixture_db, tmp_path: Path):
        g = PrereqGraph.from_db(fixture_db)
        out = tmp_path / "g.gpickle"
        g.save(out)
        loaded = PrereqGraph.load(out)
        assert loaded.graph.number_of_nodes() == g.graph.number_of_nodes()
        assert loaded.graph.number_of_edges() == g.graph.number_of_edges()


class TestPrereqSatisfaction:
    """The most-tested logic: prereq satisfaction with OR-clauses."""

    def test_no_prereqs(self, fixture_db):
        g = PrereqGraph.from_db(fixture_db)
        ok, reasons = g.prereqs_satisfied("CSS 142", {})
        assert ok
        assert reasons == []

    def test_simple_required(self, fixture_db):
        g = PrereqGraph.from_db(fixture_db)
        # CSS 422 requires CSS 342 alone
        ok, _ = g.prereqs_satisfied("CSS 422", {})
        assert not ok
        ok, _ = g.prereqs_satisfied("CSS 422", {"CSS 342": "3.0"})
        assert ok

    def test_or_clause_either_path(self, fixture_db):
        """CSS 360 requires CSS 143 OR CSE 143."""
        g = PrereqGraph.from_db(fixture_db)
        # Neither path → fail
        ok, _ = g.prereqs_satisfied("CSS 360", {})
        assert not ok
        # CSS 143 path → ok
        ok, _ = g.prereqs_satisfied("CSS 360", {"CSS 143": "2.5"})
        assert ok
        # CSE 143 path → ok (transfer-equivalent)
        ok, _ = g.prereqs_satisfied("CSS 360", {"CSE 143": "3.0"})
        assert ok

    def test_min_grade_enforcement(self, fixture_db):
        g = PrereqGraph.from_db(fixture_db)
        # default min grade is 2.0
        ok, _ = g.prereqs_satisfied("CSS 422", {"CSS 342": "1.5"})
        assert not ok
        ok, _ = g.prereqs_satisfied("CSS 422", {"CSS 342": "2.0"})
        assert ok

    def test_withdrawn_grade_does_not_satisfy(self, fixture_db):
        g = PrereqGraph.from_db(fixture_db)
        ok, _ = g.prereqs_satisfied("CSS 422", {"CSS 342": "W"})
        assert not ok

    def test_credit_no_credit_satisfies(self, fixture_db):
        g = PrereqGraph.from_db(fixture_db)
        ok, _ = g.prereqs_satisfied("CSS 422", {"CSS 342": "CR"})
        assert ok

    def test_concurrent_prereq(self, fixture_db):
        """CSS 343 lists CSS 301 as concurrent and CSS 342 as required.

        With allow_concurrent=True (default), CSS 301 being missing is
        flagged but treated leniently.
        """
        g = PrereqGraph.from_db(fixture_db)
        ok, reasons = g.prereqs_satisfied(
            "CSS 343",
            {"CSS 342": "3.0", "CSS 301": "2.5"},
        )
        assert ok
        # Without CSS 301, still passes (concurrent → leniency)
        ok, reasons = g.prereqs_satisfied(
            "CSS 343",
            {"CSS 342": "3.0"},
            allow_concurrent=True,
        )
        assert ok


class TestGradeHelper:
    @pytest.mark.parametrize(
        "grade, expected",
        [
            ("3.5", True),
            ("2.0", True),
            ("1.9", False),
            ("CR", True),
            ("W", False),
            ("I", False),
            ("NC", False),
            ("", False),
            (None, False),
        ],
    )
    def test_grade_meets_default_2_0(self, grade, expected):
        assert _grade_meets(grade, None) is expected

    def test_grade_meets_custom_min(self):
        assert _grade_meets("2.7", "2.8") is False
        assert _grade_meets("2.8", "2.8") is True
