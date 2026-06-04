"""Meeting-time parsing and time-preference matching.

The UW time schedule stores meeting times as bare ``HHMM`` strings with
**no** am/pm marker (e.g. ``"1115"``, ``"145"``, ``"545"``). The am/pm is
recoverable by convention:

* start hours 8–11  → AM
* start hour 12      → noon (12 PM)
* start hours 1–7    → PM

For a section's *end* time we parse with the same convention and then bump
it by 12 hours if that would place it before the start (e.g. ``"1130–1220"``
is 11:30 AM → 12:20 PM, and ``"1130–110"`` is 11:30 AM → 1:10 PM).

This module turns those raw strings into minutes-since-midnight, parses the
day tokens (``"TTh"`` → ``{"T", "Th"}``), and parses a free-form user
preference sentence ("prefer mornings", "nothing on Fridays", "before 3pm")
into a :class:`TimePreference` that can accept/reject a section.

Everything here is deterministic — it runs *before* the LLM so the model
never has to reason about ambiguous clock strings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ── Day tokens ───────────────────────────────────────────────────────────

# Order matters: two-letter "Th" must be tried before single-letter "T".
_DAY_TOKENS = ["M", "Th", "T", "W", "F", "Sa", "Su"]

# Map free-form day words → canonical token used in the schedule.
_DAY_WORDS = {
    "monday": "M",
    "mon": "M",
    "tuesday": "T",
    "tues": "T",
    "tue": "T",
    "wednesday": "W",
    "wed": "W",
    "thursday": "Th",
    "thurs": "Th",
    "thu": "Th",
    "friday": "F",
    "fri": "F",
    "saturday": "Sa",
    "sat": "Sa",
    "sunday": "Su",
    "sun": "Su",
}


def parse_days(token: str | None) -> set[str]:
    """Parse a schedule day string like ``"TTh"`` into ``{"T", "Th"}``.

    Unrecognized characters are skipped. Returns an empty set for
    ``None``/empty (e.g. async/online sections with no fixed day).
    """
    if not token:
        return set()
    out: set[str] = set()
    i = 0
    s = token.strip()
    while i < len(s):
        for tok in _DAY_TOKENS:
            if s[i : i + len(tok)] == tok:
                out.add(tok)
                i += len(tok)
                break
        else:
            i += 1  # skip separators / unknown chars
    return out


# ── Clock parsing ────────────────────────────────────────────────────────


def parse_uw_time(hhmm: str | None, *, assume_pm: bool | None = None) -> int | None:
    """Convert a bare ``HHMM`` UW time string to minutes-since-midnight.

    ``"1115"`` → 675 (11:15 AM), ``"145"`` → 825 (1:45 PM),
    ``"545"`` → 1065 (5:45 PM).

    ``assume_pm`` overrides the hour-based am/pm heuristic (used for end
    times that have already been determined to be PM). When ``None`` the
    convention is applied: hours 8–11 are AM, hour 12 is noon, hours 1–7
    are PM.
    """
    if not hhmm:
        return None
    s = re.sub(r"[^0-9]", "", str(hhmm))
    if not s or len(s) < 3:
        return None
    hour = int(s[:-2])
    minute = int(s[-2:])
    if hour > 23 or minute > 59:
        return None

    if assume_pm is None:
        pm = (hour <= 7) or (hour == 12)
    else:
        pm = assume_pm

    if hour == 12:
        h24 = 12 if pm else 0
    else:
        h24 = hour + 12 if pm else hour
    return h24 * 60 + minute


def parse_section_window(
    time_start: str | None, time_end: str | None
) -> tuple[int, int] | None:
    """Return ``(start_min, end_min)`` for a section, or ``None``.

    Applies the UW am/pm convention to the start, parses the end with the
    same convention, then bumps the end by 12 h if it lands before the
    start (handles morning→afternoon spans like 11:30→12:20).
    """
    start = parse_uw_time(time_start)
    if start is None:
        return None
    end = parse_uw_time(time_end)
    if end is None:
        # Unknown end — assume a 1-hour block so a start-based window still works.
        end = start + 60
    if end < start:
        end += 12 * 60
    return start, end


def _fmt_clock(minutes: int) -> str:
    """Format minutes-since-midnight as a human ``h:MM AM/PM`` string."""
    h, m = divmod(minutes % (24 * 60), 60)
    suffix = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {suffix}"


def format_time_window(time_start: str | None, time_end: str | None) -> str | None:
    """Human-readable ``"11:15 AM – 12:20 PM"`` for a section, or ``None``.

    This is what the LLM should see instead of the ambiguous raw
    ``"1115–1220"`` form.
    """
    win = parse_section_window(time_start, time_end)
    if win is None:
        return None
    start, end = win
    return f"{_fmt_clock(start)} – {_fmt_clock(end)}"


# ── User time preferences ────────────────────────────────────────────────

# Period windows in minutes-since-midnight (inclusive ranges a section must
# fit entirely within).
_NOON = 12 * 60
_EVENING = 17 * 60  # 5:00 PM


@dataclass
class TimePreference:
    """A parsed free-form time preference.

    A section *fits* when:
      * none of its meeting days are in ``excluded_days``, AND
      * its start ≥ ``earliest_start`` (when set), AND
      * its end ≤ ``latest_end`` (when set).

    Sections with no fixed meeting time (async/online) always fit — they
    can't violate a clock preference.
    """

    earliest_start: int | None = None  # minutes-since-midnight
    latest_end: int | None = None  # minutes-since-midnight
    excluded_days: set[str] = field(default_factory=set)

    def is_active(self) -> bool:
        return (
            self.earliest_start is not None
            or self.latest_end is not None
            or bool(self.excluded_days)
        )

    def _tighten_start(self, minutes: int) -> None:
        if self.earliest_start is None or minutes > self.earliest_start:
            self.earliest_start = minutes

    def _tighten_end(self, minutes: int) -> None:
        if self.latest_end is None or minutes < self.latest_end:
            self.latest_end = minutes


def _parse_clock_phrase(text: str) -> int | None:
    """Parse "3pm", "3:30 pm", "15:00", "10 am" → minutes-since-midnight."""
    m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)?", text)
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2) or 0)
    ampm = (m.group(3) or "").replace(".", "").lower()
    if ampm == "pm" and hour != 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0
    elif not ampm and hour <= 7:
        # bare small number — assume afternoon per UW convention
        hour += 12
    if hour > 23 or minute > 59:
        return None
    return hour * 60 + minute


def parse_time_preference(prompt: str | None) -> TimePreference:
    """Extract a :class:`TimePreference` from a free-form sentence.

    Recognizes period words (morning/afternoon/evening), explicit
    ``before <time>`` / ``after <time>`` windows, and day exclusions
    (``no Fridays``, ``nothing on Mondays``, ``not on Wed``). Anything it
    can't parse is simply ignored — an empty/inactive preference never
    filters anything out.
    """
    pref = TimePreference()
    if not prompt:
        return pref
    text = prompt.lower()

    # Period words.
    if re.search(r"\bmornings?\b", text):
        pref._tighten_end(_NOON)
    if re.search(r"\bafternoons?\b", text):
        pref._tighten_start(_NOON)
        pref._tighten_end(_EVENING)
    if re.search(r"\b(evenings?|nights?)\b", text):
        pref._tighten_start(_EVENING)

    # Explicit "before <time>" / "after <time>".
    for m in re.finditer(
        r"\bbefore\s+(\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?|\d{1,2}:\d{2})", text
    ):
        mins = _parse_clock_phrase(m.group(1))
        if mins is not None:
            pref._tighten_end(mins)
    for m in re.finditer(
        r"\bafter\s+(\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?|\d{1,2}:\d{2})", text
    ):
        mins = _parse_clock_phrase(m.group(1))
        if mins is not None:
            pref._tighten_start(mins)

    # Day exclusions: "no fridays", "nothing on mondays", "not on wed",
    # "avoid thursday".
    for m in re.finditer(
        r"\b(?:no|not|nothing|avoid|without|skip)\b[^.;,]*?\b("
        r"mondays?|mon|tuesdays?|tues?|wednesdays?|wed|thursdays?|thurs?|thu|"
        r"fridays?|fri|saturdays?|sat|sundays?|sun)\b",
        text,
    ):
        word = m.group(1).rstrip("s")
        tok = _DAY_WORDS.get(word) or _DAY_WORDS.get(word + "s")
        if tok:
            pref.excluded_days.add(tok)

    return pref


def section_fits(section: dict, pref: TimePreference) -> bool:
    """Return True if a single section satisfies ``pref``.

    ``section`` is a dict with ``days``, ``time_start``, ``time_end``
    (the shape produced by ``Recommender._lookup_sections``).
    """
    if not pref.is_active():
        return True

    days = parse_days(section.get("days"))
    if pref.excluded_days and days & pref.excluded_days:
        return False

    win = parse_section_window(section.get("time_start"), section.get("time_end"))
    if win is None:
        # No fixed meeting time → can't violate a clock window.
        return True
    start, end = win
    if pref.earliest_start is not None and start < pref.earliest_start:
        return False
    if pref.latest_end is not None and end > pref.latest_end:
        return False
    return True


def course_fits(meetings: list[dict] | None, pref: TimePreference) -> bool:
    """Return True if a course has *at least one* section that fits ``pref``.

    A course with no scheduled sections fits (nothing to violate) — the
    eligibility/offering filters elsewhere already decide whether it's a
    real candidate.
    """
    if not pref.is_active():
        return True
    if not meetings:
        return True
    return any(section_fits(m, pref) for m in meetings)
