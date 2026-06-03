"""Tests for the deterministic meeting-time / time-preference layer."""

from __future__ import annotations

from capstone.scheduling import (
    TimePreference,
    course_fits,
    format_time_window,
    parse_days,
    parse_section_window,
    parse_time_preference,
    parse_uw_time,
    section_fits,
)


# ── Day parsing ──────────────────────────────────────────────────────────


def test_parse_days_two_letter_thursday():
    assert parse_days("TTh") == {"T", "Th"}


def test_parse_days_mwf():
    assert parse_days("MWF") == {"M", "W", "F"}


def test_parse_days_empty_and_none():
    assert parse_days("") == set()
    assert parse_days(None) == set()


# ── Clock parsing (UW am/pm convention) ──────────────────────────────────


def test_parse_uw_time_morning():
    assert parse_uw_time("1115") == 11 * 60 + 15  # 11:15 AM


def test_parse_uw_time_afternoon():
    assert parse_uw_time("145") == 13 * 60 + 45  # 1:45 PM


def test_parse_uw_time_evening():
    assert parse_uw_time("545") == 17 * 60 + 45  # 5:45 PM


def test_parse_uw_time_noon():
    assert parse_uw_time("1200") == 12 * 60  # noon


def test_parse_uw_time_garbage():
    assert parse_uw_time(None) is None
    assert parse_uw_time("") is None
    assert parse_uw_time("12") is None  # too short to carry minutes


def test_parse_section_window_morning_to_afternoon():
    # 11:30 AM → 12:20 PM (end parses as noon, stays after start)
    assert parse_section_window("1130", "1220") == (11 * 60 + 30, 12 * 60 + 20)


def test_parse_section_window_crosses_noon_bump():
    # 11:30 AM → 1:10 PM: end "110" would parse before start, gets bumped
    res = parse_section_window("1130", "110")
    assert res is not None
    start, end = res
    assert start == 11 * 60 + 30
    assert end == 13 * 60 + 10


def test_format_time_window_human_readable():
    assert format_time_window("1115", "1220") == "11:15 AM – 12:20 PM"
    assert format_time_window("145", "245") == "1:45 PM – 2:45 PM"


# ── Preference parsing ───────────────────────────────────────────────────


def test_parse_pref_mornings():
    pref = parse_time_preference("I prefer morning classes")
    assert pref.is_active()
    assert pref.latest_end == 12 * 60


def test_parse_pref_evenings():
    pref = parse_time_preference("only evening classes please")
    assert pref.earliest_start == 17 * 60


def test_parse_pref_no_fridays():
    pref = parse_time_preference("nothing on Fridays")
    assert "F" in pref.excluded_days


def test_parse_pref_before_after():
    pref = parse_time_preference("classes after 10am and before 3pm")
    assert pref.earliest_start == 10 * 60
    assert pref.latest_end == 15 * 60


def test_parse_pref_inactive_when_no_signal():
    pref = parse_time_preference("I like project-heavy classes")
    assert not pref.is_active()


# ── Section / course matching ────────────────────────────────────────────


def _section(days, ts, te):
    return {"days": days, "time_start": ts, "time_end": te}


def test_section_fits_morning_pref():
    pref = parse_time_preference("mornings only")
    assert section_fits(_section("MWF", "930", "1020"), pref)  # 9:30–10:20 AM
    assert not section_fits(_section("MWF", "145", "245"), pref)  # afternoon


def test_section_fits_excluded_day():
    pref = parse_time_preference("no Fridays")
    assert not section_fits(_section("F", "930", "1020"), pref)
    assert section_fits(_section("TTh", "930", "1020"), pref)


def test_section_with_no_time_always_fits():
    pref = parse_time_preference("mornings only")
    assert section_fits(_section(None, None, None), pref)


def test_course_fits_if_any_section_fits():
    pref = parse_time_preference("mornings only")
    meetings = [
        _section("MWF", "145", "245"),  # afternoon — no
        _section("TTh", "930", "1020"),  # morning — yes
    ]
    assert course_fits(meetings, pref)


def test_course_does_not_fit_when_all_sections_conflict():
    pref = parse_time_preference("mornings only")
    meetings = [_section("MWF", "145", "245"), _section("TTh", "300", "400")]
    assert not course_fits(meetings, pref)


def test_inactive_pref_accepts_everything():
    pref = TimePreference()
    assert course_fits([_section("F", "145", "245")], pref)
    assert section_fits(_section("F", "145", "245"), pref)
