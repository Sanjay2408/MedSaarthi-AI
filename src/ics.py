"""Reminders as an iCalendar file (RFC 5545). Opens in the calendar app on any phone and rings at
each dose time, with no push server and no app store. Times are written as "floating" local times,
so 8:00 AM stays 8:00 AM wherever the phone is. Each dose time is one daily-repeating event that
ends when the course does.
"""
import re
import uuid
from datetime import date, datetime, timedelta, timezone

_DURATION = re.compile(r"(\d+(?:\.\d+)?)\s*(day|week|month)s?", re.IGNORECASE)
_DAYS = {"day": 1, "week": 7, "month": 30}
DEFAULT_DAYS = 30   # open-ended courses get a month of reminders, renewed with the prescription
MAX_DAYS = 365


def course_days(duration: str | None) -> int | None:
    """Whole days in a duration like '5 days' or '2 weeks'; None when it can't be counted."""
    m = _DURATION.search(duration or "")
    if not m:
        return None
    return max(1, min(MAX_DAYS, round(float(m.group(1)) * _DAYS[m.group(2).lower()])))


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n")


def _fold(line: str) -> list[str]:
    """Lines longer than 75 octets continue on the next line after a space (never inside a character)."""
    out, cur, size = [], "", 0
    for ch in line:
        n = len(ch.encode("utf-8"))
        if size + n > 75:
            out.append(cur)
            cur, size = " " + ch, 1 + n
        else:
            cur, size = cur + ch, size + n
    out.append(cur)
    return out


def build_ics(entries: list[dict], start: date, now: datetime | None = None) -> str:
    """entries: [{"medicine", "dose", "times": ["08:00", ...], "days": int | None, "how": str}].
    A medicine with no fixed times (only when needed) gets no events."""
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//MedSaarthi AI//Medicine plan//EN", "CALSCALE:GREGORIAN",
             "X-WR-CALNAME:Medicine plan"]
    for e in entries:
        days = e.get("days") or DEFAULT_DAYS
        for t in e["times"]:
            h, m = map(int, t.split(":"))
            begin = datetime(start.year, start.month, start.day, h, m)
            end = begin + timedelta(minutes=10)
            title = f"Take {e['medicine']} {e['dose']}"
            lines += ["BEGIN:VEVENT", f"UID:{uuid.uuid4().hex}@medsaarthi", f"DTSTAMP:{stamp}",
                      f"DTSTART:{begin.strftime('%Y%m%dT%H%M%S')}", f"DTEND:{end.strftime('%Y%m%dT%H%M%S')}",
                      f"RRULE:FREQ=DAILY;COUNT={days}", f"SUMMARY:{_escape(title)}"]
            if e.get("how"):
                lines.append(f"DESCRIPTION:{_escape(e['how'])}")
            lines += ["BEGIN:VALARM", "TRIGGER:PT0M", "ACTION:DISPLAY", f"DESCRIPTION:{_escape(title)}", "END:VALARM", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(part for line in lines for part in _fold(line)) + "\r\n"
