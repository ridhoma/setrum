"""Shared formatters for annotation labels and hover-tooltip text."""

from __future__ import annotations

import pandas as pd


def format_period(start: pd.Timestamp, end: pd.Timestamp) -> str:
    """Compact, human-readable period label.

      * sub-day same-date → 'Mon 15 Apr · 07:00 → 08:00'
      * full single day  → 'Mon 15 Apr'
      * multi-day        → 'Mon 15 Apr → Wed 17 Apr'
    """
    if start.date() == end.date():
        return f"{start.strftime('%a %d %b')} · {start.strftime('%H:%M')} → {end.strftime('%H:%M')}"
    # Daily annotations have an exclusive next-midnight end; show the last
    # included day instead.
    end_label = end if end.time() != pd.Timestamp("00:00").time() else end - pd.Timedelta(days=1)
    if start.date() == end_label.date():
        return start.strftime("%a %d %b")
    return f"{start.strftime('%a %d %b')} → {end_label.strftime('%a %d %b')}"


def split_pipe(value) -> list[str]:
    """Split a `GROUP_CONCAT(... '|')` field; treat None/NaN as empty."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    return [p for p in str(value).split("|") if p and p != "None"]


def safe_str(value) -> str:
    """Coerce a possibly-NaN cell to string (pandas reads SQL NULL as NaN)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value)


def hover_text(ann) -> str:
    """Compact HTML hover text for an annotation overlay icon — period and
    comment only. Tags / aggregate stats live on the sticky-note board.
    """
    parts: list[str] = []

    start = pd.to_datetime(ann["period_start_utc"])
    end   = pd.to_datetime(ann["period_end_utc"])
    parts.append(f"<b>{format_period(start, end)}</b>")

    comment = safe_str(ann.get("comment")).strip()
    if comment:
        parts.append(comment)

    return "<br>".join(parts)
