"""Bounded read-side queries for consumption data and analytics-table aggregates.

Replaces ad-hoc pandas filtering in `ui/sections/*.py` and the unbounded
table scans in `ui/data.py`. Every function accepts an optional account_id
filter and either accepts an external connection or opens its own.
"""

from __future__ import annotations

import datetime
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


def _account_clause(account_id: int | None, alias: str = "") -> tuple[str, list]:
    if account_id is None:
        return "", []
    prefix = f"{alias}." if alias else ""
    return f" AND {prefix}account_id = ?", [account_id]


def get_half_hourly(
    start_utc: str,
    end_utc: str,
    account_id: int | None = None,
    conn: sqlite3.Connection | None = None,
) -> pd.DataFrame:
    """Half-hourly consumption rows in `[start_utc, end_utc)`.

    Both bounds are TEXT compared against `interval_start_at_utc`. Any
    ISO-8601 prefix that sorts lexicographically against the stored values
    works (e.g. 'YYYY-MM-DD' or full timestamps).
    """
    extra, extra_params = _account_clause(account_id)
    query = f"""
        SELECT *
        FROM analytics_fct_consumptions_half_hourly
        WHERE interval_start_at_utc >= ?
          AND interval_start_at_utc < ?
          {extra}
        ORDER BY interval_start_at_utc ASC
    """
    with _conn(conn) as c:
        df = pd.read_sql_query(query, c, params=[start_utc, end_utc, *extra_params])
    if not df.empty:
        df["interval_start_at_utc"] = pd.to_datetime(df["interval_start_at_utc"])
        df["interval_end_at_utc"] = pd.to_datetime(df["interval_end_at_utc"])
    return df


def get_daily_summary(
    start_date: str,
    end_date: str,
    account_id: int | None = None,
    conn: sqlite3.Connection | None = None,
) -> pd.DataFrame:
    """Daily summary rows in `[start_date, end_date]` (both inclusive).

    `date` comes back as tz-aware UTC so it lines up on the same timeline
    as annotation periods (which are stored as ISO with explicit offset).
    Without this, naive midnights get parsed as local-time in the browser
    and the annotation overlay rectangles drift by the user's UTC offset.
    """
    extra, extra_params = _account_clause(account_id)
    query = f"""
        SELECT *
        FROM analytics_fct_consumptions_daily
        WHERE date >= ?
          AND date <= ?
          {extra}
        ORDER BY date ASC
    """
    with _conn(conn) as c:
        df = pd.read_sql_query(query, c, params=[start_date, end_date, *extra_params])
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize("UTC")
    return df


def aggregate_period(
    start_utc: str,
    end_utc: str,
    account_id: int | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict:
    """Sum kWh and cost across `[start_utc, end_utc)`.

    Used live by the annotation form prefill. Returns zeros when the range
    is empty so the UI can render unconditionally.
    """
    extra, extra_params = _account_clause(account_id)
    query = f"""
        SELECT
            COALESCE(SUM(consumption_kwh), 0)             AS kwh,
            COALESCE(SUM(consumption_pence_exc_vat), 0)   AS cost_pence_exc_vat,
            COALESCE(SUM(consumption_pence_inc_vat), 0)   AS cost_pence_inc_vat,
            COUNT(*)                                      AS n_intervals
        FROM analytics_fct_consumptions_half_hourly
        WHERE interval_start_at_utc >= ?
          AND interval_start_at_utc < ?
          {extra}
    """
    with _conn(conn) as c:
        cur = c.execute(query, [start_utc, end_utc, *extra_params])
        row = cur.fetchone()
    return {
        "kwh": float(row["kwh"]) if row["kwh"] is not None else 0.0,
        "cost_pence_exc_vat": float(row["cost_pence_exc_vat"] or 0.0),
        "cost_pence_inc_vat": float(row["cost_pence_inc_vat"] or 0.0),
        "n_intervals": int(row["n_intervals"] or 0),
        "start_utc": start_utc,
        "end_utc": end_utc,
    }


def get_summary_metrics(
    start_date: str,
    end_date: str,
    account_id: int | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict:
    """Sum daily totals over `[start_date, end_date]` (both inclusive).

    The four KPIs come straight from the daily fact: total kWh, total cost
    incl. VAT, volume-weighted average unit price incl. VAT, and the mean
    standing charge per day.
    """
    extra, extra_params = _account_clause(account_id)
    with _conn(conn) as c:
        agg = c.execute(
            f"""
            SELECT
                COALESCE(SUM(consumption_kwh), 0)               AS total_kwh,
                COALESCE(SUM(total_pence_inc_vat), 0)           AS total_pence_inc_vat,
                COALESCE(SUM(consumption_pence_inc_vat), 0)     AS total_consumption_pence_inc_vat,
                COALESCE(AVG(standing_charge_pence_inc_vat), 0) AS avg_standing_pence_inc_vat
            FROM analytics_fct_consumptions_daily
            WHERE date >= ? AND date <= ? {extra}
            """,
            [start_date, end_date, *extra_params],
        ).fetchone()

    total_kwh = float(agg["total_kwh"] or 0.0)
    total_cost = float(agg["total_pence_inc_vat"] or 0.0) / 100.0
    avg_price_inc = (
        float(agg["total_consumption_pence_inc_vat"] or 0.0) / total_kwh
        if total_kwh > 0
        else 0.0
    )
    avg_standing = float(agg["avg_standing_pence_inc_vat"] or 0.0) / 100.0
    return {
        "total_kwh": total_kwh,
        "total_cost_inc_vat": total_cost,
        "avg_price_inc_vat": avg_price_inc,
        "avg_standing_charge": avg_standing,
        "window_from": start_date,
        "window_to": end_date,
    }


def get_data_extent(
    account_id: int | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict:
    """Min/max timestamps available for date-picker bounds."""
    extra, extra_params = _account_clause(account_id)
    with _conn(conn) as c:
        hh = c.execute(
            f"""
            SELECT MIN(interval_start_at_utc) AS hh_min,
                   MAX(interval_start_at_utc) AS hh_max
            FROM analytics_fct_consumptions_half_hourly
            WHERE 1=1 {extra}
            """,
            extra_params,
        ).fetchone()
        daily = c.execute(
            f"""
            SELECT MIN(date) AS daily_min,
                   MAX(date) AS daily_max
            FROM analytics_fct_consumptions_daily
            WHERE 1=1 {extra}
            """,
            extra_params,
        ).fetchone()
    return {
        "hh_min": hh["hh_min"] if hh else None,
        "hh_max": hh["hh_max"] if hh else None,
        "daily_min": daily["daily_min"] if daily else None,
        "daily_max": daily["daily_max"] if daily else None,
    }
