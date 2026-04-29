"""Annotation CRUD: time-range notes with tags, written transactionally.

Tags are looked up case-insensitively via `services.tags.get_or_create`,
so saving the same tag name in any case never fragments the analytics.

Period bounds are stored as ISO-8601 UTC strings to match the convention
of `source_consumptions.interval_start`. Callers may snap to half-hour
boundaries before saving (recommended) or save exact brush timestamps —
the join in `tags.consumption_by_tag` works on `>=` / `<` regardless.
"""

from __future__ import annotations

import datetime
import sqlite3
from contextlib import contextmanager
from typing import Iterator

import pandas as pd

from core.database import get_connection
from core.services import tags as tags_service

VALID_SOURCES = ("daily", "half-hourly")


def _validate_source(source: str) -> str:
    if source not in VALID_SOURCES:
        raise ValueError(f"source must be one of {VALID_SOURCES!r}, got {source!r}")
    return source


def snap_to_half_hour(ts_iso: str, *, direction: str = "down") -> str:
    """Round an ISO-8601 timestamp to the nearest half-hour boundary.

    `direction='down'` floors (use for `period_start`), `'up'` ceils
    (use for `period_end`). Bare timestamps without timezone info are
    assumed to be UTC; the result always carries an explicit offset.
    """
    if direction not in ("down", "up"):
        raise ValueError("direction must be 'down' or 'up'")
    dt = datetime.datetime.fromisoformat(ts_iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    base = dt.replace(minute=0, second=0, microsecond=0)
    minutes_into = (dt - base).total_seconds() / 60.0
    if direction == "down":
        slot = 0 if minutes_into < 30 else 30
        snapped = base.replace(minute=slot)
    else:
        if minutes_into == 0:
            snapped = base
        elif minutes_into <= 30:
            snapped = base.replace(minute=30)
        else:
            snapped = base + datetime.timedelta(hours=1)
    return snapped.isoformat()


@contextmanager
def _conn(conn: sqlite3.Connection | None) -> Iterator[sqlite3.Connection]:
    if conn is not None:
        yield conn
        return
    new_conn = get_connection()
    try:
        yield new_conn
    finally:
        new_conn.close()


def _normalize_tag_names(tag_names: list[str] | None) -> list[str]:
    if not tag_names:
        return []
    seen: dict[str, str] = {}  # lowercase -> first-seen original (preserves order)
    for raw in tag_names:
        if raw is None:
            continue
        name = str(raw).strip()
        if not name:
            continue
        key = name.lower()
        if key not in seen:
            seen[key] = name
    return list(seen.values())


def create(
    account_id: int,
    period_start_utc: str,
    period_end_utc: str,
    source: str,
    comment: str | None = None,
    tag_names: list[str] | None = None,
    conn: sqlite3.Connection | None = None,
) -> int:
    """Insert annotation + ensure tags + link them, in one transaction.

    `source` must be one of `VALID_SOURCES` ('daily' / 'half-hourly') and
    decides which chart will draw the overlay band for this annotation.
    """
    if period_end_utc <= period_start_utc:
        raise ValueError("period_end_utc must be strictly greater than period_start_utc")
    _validate_source(source)

    tag_names = _normalize_tag_names(tag_names)

    def _do(c: sqlite3.Connection) -> int:
        cur = c.execute(
            """
            INSERT INTO annotations (account_id, period_start_utc, period_end_utc, source, comment)
            VALUES (?, ?, ?, ?, ?)
            """,
            (account_id, period_start_utc, period_end_utc, source, comment),
        )
        annotation_id = int(cur.lastrowid)
        for name in tag_names:
            tag_id = tags_service.get_or_create(name, conn=c)
            c.execute(
                "INSERT OR IGNORE INTO annotation_tags (annotation_id, tag_id) VALUES (?, ?)",
                (annotation_id, tag_id),
            )
        return annotation_id

    if conn is not None:
        return _do(conn)
    with _conn(None) as c:
        with c:
            return _do(c)


def update(
    annotation_id: int,
    comment: str | None = None,
    tag_names: list[str] | None = None,
    period_start_utc: str | None = None,
    period_end_utc: str | None = None,
    source: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> None:
    """Patch any subset of fields. Pass `tag_names=[]` to clear all tags."""
    fields = []
    params: list = []
    if comment is not None:
        fields.append("comment = ?")
        params.append(comment)
    if period_start_utc is not None:
        fields.append("period_start_utc = ?")
        params.append(period_start_utc)
    if period_end_utc is not None:
        fields.append("period_end_utc = ?")
        params.append(period_end_utc)
    if source is not None:
        _validate_source(source)
        fields.append("source = ?")
        params.append(source)

    def _do(c: sqlite3.Connection) -> None:
        if fields:
            c.execute(
                f"UPDATE annotations SET {', '.join(fields)} WHERE id = ?",
                [*params, annotation_id],
            )
        if tag_names is not None:
            normalized = _normalize_tag_names(tag_names)
            c.execute("DELETE FROM annotation_tags WHERE annotation_id = ?", (annotation_id,))
            for name in normalized:
                tag_id = tags_service.get_or_create(name, conn=c)
                c.execute(
                    "INSERT OR IGNORE INTO annotation_tags (annotation_id, tag_id) VALUES (?, ?)",
                    (annotation_id, tag_id),
                )

    if conn is not None:
        _do(conn)
        return
    with _conn(None) as c:
        with c:
            _do(c)


def set_position(
    annotation_id: int,
    x: int | None,
    y: int | None,
    conn: sqlite3.Connection | None = None,
) -> None:
    """Persist the canvas (x, y) of a sticky note. Pass `None` for either
    coord to clear it (which makes the UI auto-place the note again).
    """
    def _do(c: sqlite3.Connection) -> None:
        c.execute(
            "UPDATE annotations SET position_x = ?, position_y = ? WHERE id = ?",
            (
                int(x) if x is not None else None,
                int(y) if y is not None else None,
                int(annotation_id),
            ),
        )

    if conn is not None:
        _do(conn)
        return
    with _conn(None) as c:
        with c:
            _do(c)


def set_positions(
    records,
    conn: sqlite3.Connection | None = None,
) -> int:
    """Persist canvas (x, y) for many sticky notes in a single transaction.

    Each record is a mapping with 'id' and 'x' / 'y'. Used by multi-drag,
    where dragging a multi-selection ends with one batched update so the
    moved notes commit atomically.
    """
    def _do(c: sqlite3.Connection) -> int:
        n = 0
        for r in records:
            try:
                ann_id = int(r["id"])
            except (KeyError, TypeError, ValueError):
                continue
            x = r.get("x")
            y = r.get("y")
            c.execute(
                "UPDATE annotations SET position_x = ?, position_y = ? WHERE id = ?",
                (
                    int(x) if x is not None else None,
                    int(y) if y is not None else None,
                    ann_id,
                ),
            )
            n += 1
        return n

    if conn is not None:
        return _do(conn)
    with _conn(None) as c:
        with c:
            return _do(c)


def delete(annotation_id: int, conn: sqlite3.Connection | None = None) -> None:
    """Delete an annotation; cascade removes its annotation_tags rows."""
    def _do(c: sqlite3.Connection) -> None:
        c.execute("DELETE FROM annotations WHERE id = ?", (annotation_id,))

    if conn is not None:
        _do(conn)
        return
    with _conn(None) as c:
        with c:
            _do(c)


def get_by_id(
    annotation_id: int,
    conn: sqlite3.Connection | None = None,
) -> dict | None:
    """Return the annotation dict with its `tags` list, or None if missing."""
    with _conn(conn) as c:
        ann = c.execute("SELECT * FROM annotations WHERE id = ?", (annotation_id,)).fetchone()
        if ann is None:
            return None
        tag_rows = c.execute(
            """
            SELECT t.id, t.name, t.color
            FROM annotation_tags at
            JOIN tags t ON t.id = at.tag_id
            WHERE at.annotation_id = ?
            ORDER BY t.name COLLATE NOCASE ASC
            """,
            (annotation_id,),
        ).fetchall()
    out = dict(ann)
    out["tags"] = [dict(t) for t in tag_rows]
    return out


def list_all_with_aggregates(
    account_id: int | None = None,
    conn: sqlite3.Connection | None = None,
) -> pd.DataFrame:
    """Every annotation, with its tags and computed kWh / cost.

    Each kWh and cost field comes from a correlated subquery (not a join),
    so multiple tags don't multiply the consumption sums via cartesian
    product. Cheap enough for boards in the low hundreds; if the corkboard
    ever has thousands of notes we'd swap to a CTE.
    """
    extra = ""
    params: list = []
    if account_id is not None:
        extra = " WHERE a.account_id = ?"
        params.append(account_id)

    query = f"""
        SELECT
            a.id,
            a.account_id,
            a.period_start_utc,
            a.period_end_utc,
            a.source,
            a.comment,
            a.position_x,
            a.position_y,
            a.created_at,
            a.updated_at,
            (SELECT GROUP_CONCAT(t.name, '|')
               FROM annotation_tags at JOIN tags t ON t.id = at.tag_id
              WHERE at.annotation_id = a.id) AS tag_names,
            (SELECT GROUP_CONCAT(t.color, '|')
               FROM annotation_tags at JOIN tags t ON t.id = at.tag_id
              WHERE at.annotation_id = a.id) AS tag_colors,
            COALESCE((
                SELECT SUM(hh.consumption_kwh)
                  FROM analytics_fct_consumptions_half_hourly hh
                 WHERE hh.account_id = a.account_id
                   AND hh.interval_start_at_utc >= a.period_start_utc
                   AND hh.interval_start_at_utc <  a.period_end_utc
            ), 0) AS kwh,
            COALESCE((
                SELECT SUM(hh.consumption_pence_inc_vat)
                  FROM analytics_fct_consumptions_half_hourly hh
                 WHERE hh.account_id = a.account_id
                   AND hh.interval_start_at_utc >= a.period_start_utc
                   AND hh.interval_start_at_utc <  a.period_end_utc
            ), 0) AS cost_pence_inc_vat
        FROM annotations a
        {extra}
        ORDER BY a.created_at DESC
    """
    with _conn(conn) as c:
        df = pd.read_sql_query(query, c, params=params)
    if not df.empty:
        df["period_start_utc"] = pd.to_datetime(df["period_start_utc"])
        df["period_end_utc"] = pd.to_datetime(df["period_end_utc"])
    return df


def list_in_range(
    start_utc: str,
    end_utc: str,
    account_id: int | None = None,
    source: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> pd.DataFrame:
    """Annotations whose period overlaps `[start_utc, end_utc)`.

    Uses an *overlap* predicate, not containment: any annotation whose
    window touches the requested range is returned. Tags are flattened
    into pipe-delimited columns to keep the result a flat DataFrame.

    `source` (optional) restricts to annotations assigned to that chart
    ('daily' or 'half-hourly'). Used by chart overlay rendering so each
    chart shows only its own bands.
    """
    params: list = [start_utc, end_utc]
    extra = ""
    if account_id is not None:
        extra += " AND a.account_id = ?"
        params.append(account_id)
    if source is not None:
        _validate_source(source)
        extra += " AND a.source = ?"
        params.append(source)
    query = f"""
        SELECT
            a.id,
            a.account_id,
            a.period_start_utc,
            a.period_end_utc,
            a.source,
            a.comment,
            a.created_at,
            a.updated_at,
            GROUP_CONCAT(t.name, '|')  AS tag_names,
            GROUP_CONCAT(t.color, '|') AS tag_colors
        FROM annotations a
        LEFT JOIN annotation_tags at ON at.annotation_id = a.id
        LEFT JOIN tags t              ON t.id = at.tag_id
        WHERE a.period_end_utc > ?
          AND a.period_start_utc < ?
          {extra}
        GROUP BY a.id
        ORDER BY a.period_start_utc ASC
    """
    with _conn(conn) as c:
        df = pd.read_sql_query(query, c, params=params)
    if not df.empty:
        df["period_start_utc"] = pd.to_datetime(df["period_start_utc"])
        df["period_end_utc"] = pd.to_datetime(df["period_end_utc"])
    return df
