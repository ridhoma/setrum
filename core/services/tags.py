"""Tags + tag-based consumption analytics.

Tags are first-class analytics primitives: an annotation tagged 'breakfast'
contributes its time window to all aggregations of `consumption_by_tag('breakfast')`.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

import pandas as pd

from core.database import get_connection


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


def list_all(conn: sqlite3.Connection | None = None) -> pd.DataFrame:
    """All tags with usage count, ordered by most-used first."""
    query = """
        SELECT
            t.id,
            t.name,
            t.color,
            t.created_at,
            COALESCE(COUNT(at.annotation_id), 0) AS usage_count
        FROM tags t
        LEFT JOIN annotation_tags at ON at.tag_id = t.id
        GROUP BY t.id, t.name, t.color, t.created_at
        ORDER BY usage_count DESC, t.name COLLATE NOCASE ASC
    """
    with _conn(conn) as c:
        return pd.read_sql_query(query, c)


def get_or_create(
    name: str,
    color: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> int:
    """Return the id of the tag named `name`, creating it if missing.

    Case-insensitive match (the column itself is COLLATE NOCASE).
    """
    name = name.strip()
    if not name:
        raise ValueError("tag name must not be empty")

    def _do(c: sqlite3.Connection) -> int:
        row = c.execute(
            "SELECT id FROM tags WHERE name = ? COLLATE NOCASE", (name,)
        ).fetchone()
        if row:
            return int(row["id"])
        cur = c.execute("INSERT INTO tags (name, color) VALUES (?, ?)", (name, color))
        return int(cur.lastrowid)

    if conn is not None:
        return _do(conn)
    with _conn(None) as c:
        with c:
            return _do(c)


def consumption_by_tag(
    tag_name: str,
    start_utc: str | None = None,
    end_utc: str | None = None,
    account_id: int | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict:
    """Total kWh and cost across every annotation carrying this tag.

    Joins each annotation's `[period_start_utc, period_end_utc)` window
    into the half-hourly fact table. Optional outer date bounds clip
    annotations to a given range; if either bound is omitted, the
    annotation's own period is used.
    """
    params: list = [tag_name]
    range_clause = ""
    if start_utc is not None:
        range_clause += " AND a.period_end_utc > ?"
        params.append(start_utc)
    if end_utc is not None:
        range_clause += " AND a.period_start_utc < ?"
        params.append(end_utc)

    account_clause = ""
    if account_id is not None:
        account_clause = " AND a.account_id = ? AND hh.account_id = ?"
        params.extend([account_id, account_id])

    query = f"""
        SELECT
            COALESCE(SUM(hh.consumption_kwh), 0)             AS kwh,
            COALESCE(SUM(hh.consumption_pence_exc_vat), 0)   AS cost_exc_vat,
            COALESCE(SUM(hh.consumption_pence_inc_vat), 0)   AS cost_inc_vat,
            COUNT(DISTINCT a.id)                             AS n_annotations
        FROM annotations a
        JOIN annotation_tags at ON at.annotation_id = a.id
        JOIN tags t              ON t.id = at.tag_id AND t.name = ? COLLATE NOCASE
        JOIN analytics_fct_consumptions_half_hourly hh
          ON hh.account_id = a.account_id
         AND hh.interval_start_at_utc >= a.period_start_utc
         AND hh.interval_start_at_utc <  a.period_end_utc
        WHERE 1=1 {range_clause} {account_clause}
    """
    with _conn(conn) as c:
        row = c.execute(query, params).fetchone()
    return {
        "tag": tag_name,
        "kwh": float(row["kwh"] or 0.0),
        "cost_exc_vat": float(row["cost_exc_vat"] or 0.0),
        "cost_inc_vat": float(row["cost_inc_vat"] or 0.0),
        "n_annotations": int(row["n_annotations"] or 0),
    }


def timeseries_by_tag(
    tag_name: str,
    start_utc: str | None = None,
    end_utc: str | None = None,
    account_id: int | None = None,
    conn: sqlite3.Connection | None = None,
) -> pd.DataFrame:
    """Per-day kWh/cost contribution of a tag — for trend charts."""
    params: list = [tag_name]
    range_clause = ""
    if start_utc is not None:
        range_clause += " AND a.period_end_utc > ?"
        params.append(start_utc)
    if end_utc is not None:
        range_clause += " AND a.period_start_utc < ?"
        params.append(end_utc)

    account_clause = ""
    if account_id is not None:
        account_clause = " AND a.account_id = ? AND hh.account_id = ?"
        params.extend([account_id, account_id])

    query = f"""
        SELECT
            date(hh.interval_start_at_utc) AS date,
            SUM(hh.consumption_kwh)             AS kwh,
            SUM(hh.consumption_pence_exc_vat)   AS cost_exc_vat,
            SUM(hh.consumption_pence_inc_vat)   AS cost_inc_vat,
            COUNT(DISTINCT a.id)                AS n_annotations
        FROM annotations a
        JOIN annotation_tags at ON at.annotation_id = a.id
        JOIN tags t              ON t.id = at.tag_id AND t.name = ? COLLATE NOCASE
        JOIN analytics_fct_consumptions_half_hourly hh
          ON hh.account_id = a.account_id
         AND hh.interval_start_at_utc >= a.period_start_utc
         AND hh.interval_start_at_utc <  a.period_end_utc
        WHERE 1=1 {range_clause} {account_clause}
        GROUP BY date(hh.interval_start_at_utc)
        ORDER BY date(hh.interval_start_at_utc) ASC
    """
    with _conn(conn) as c:
        df = pd.read_sql_query(query, c, params=params)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df
