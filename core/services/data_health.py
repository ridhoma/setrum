"""Data health and availability service.

Provides data completeness metrics, daily availability maps for GitHub-style
tile visualisations, and orchestrates chunked historical backfills.
"""

from __future__ import annotations

import datetime
import sqlite3
from contextlib import contextmanager
from typing import Callable, Iterator, Optional

import pandas as pd

from core import orchestrator
from core.database import get_connection

ProgressCb = Callable[[str, int, int], None]


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


def get_accounts(conn: sqlite3.Connection | None = None) -> list[dict]:
    """Return all accounts/properties with metadata."""
    with _conn(conn) as c:
        rows = c.execute(
            """
            SELECT account_id, account_number, address_line_1, town, postcode,
                   moved_in_at, moved_out_at
            FROM source_accounts
            ORDER BY (moved_out_at IS NULL) DESC, moved_in_at DESC
            """
        ).fetchall()

    out = []
    for r in rows:
        d = dict(r)
        d["is_active"] = d["moved_out_at"] is None
        addr_parts = [p for p in [d.get("address_line_1"), d.get("town"), d.get("postcode")] if p]
        d["display_name"] = ", ".join(addr_parts) if addr_parts else f"Account {d['account_id']}"
        if d["is_active"]:
            d["display_name"] += " (Current)"
        out.append(d)
    return out


def get_raw_tables_overview(account_id: int | None = None, conn: sqlite3.Connection | None = None) -> list[dict]:
    """Overview statistics for all raw and analytics tables."""
    with _conn(conn) as c:
        # 1. source_consumptions
        row_c = c.execute(
            """
            SELECT COUNT(*) AS cnt,
                   MIN(interval_start) AS min_ts,
                   MAX(interval_start) AS max_ts
            FROM source_consumptions
            """
        ).fetchone()

        # 2. source_electricity_standard_unit_rates
        row_u = c.execute(
            """
            SELECT COUNT(*) AS cnt,
                   MIN(interval_start) AS min_ts,
                   MAX(interval_start) AS max_ts
            FROM source_electricity_standard_unit_rates
            """
        ).fetchone()

        # 3. source_electricity_standing_charges
        row_s = c.execute(
            """
            SELECT COUNT(*) AS cnt,
                   MIN(interval_start) AS min_ts,
                   MAX(interval_start) AS max_ts
            FROM source_electricity_standing_charges
            """
        ).fetchone()

        # 4. analytics_fct_consumptions_daily
        row_a = c.execute(
            """
            SELECT COUNT(*) AS cnt,
                   MIN(date) AS min_ts,
                   MAX(date) AS max_ts
            FROM analytics_fct_consumptions_daily
            """
        ).fetchone()

    def _fmt_ts(val: str | None) -> str:
        if not val:
            return "—"
        return val[:10]

    return [
        {
            "id": "source_consumptions",
            "name": "Half-Hourly Consumption",
            "table": "source_consumptions",
            "description": "Raw smart meter electricity readings (48 intervals/day)",
            "count": row_c["cnt"] if row_c else 0,
            "earliest": _fmt_ts(row_c["min_ts"] if row_c else None),
            "latest": _fmt_ts(row_c["max_ts"] if row_c else None),
            "status": "Healthy" if (row_c and row_c["cnt"] > 0) else "Empty",
            "badge_color": "success" if (row_c and row_c["cnt"] > 0) else "secondary",
        },
        {
            "id": "source_electricity_standard_unit_rates",
            "name": "Standard Unit Rates",
            "table": "source_electricity_standard_unit_rates",
            "description": "Octopus tariff pricing intervals (p/kWh)",
            "count": row_u["cnt"] if row_u else 0,
            "earliest": _fmt_ts(row_u["min_ts"] if row_u else None),
            "latest": _fmt_ts(row_u["max_ts"] if row_u else None),
            "status": "Healthy" if (row_u and row_u["cnt"] > 0) else "Empty",
            "badge_color": "success" if (row_u and row_u["cnt"] > 0) else "secondary",
        },
        {
            "id": "source_electricity_standing_charges",
            "name": "Standing Charges",
            "table": "source_electricity_standing_charges",
            "description": "Daily standing connection charges (p/day)",
            "count": row_s["cnt"] if row_s else 0,
            "earliest": _fmt_ts(row_s["min_ts"] if row_s else None),
            "latest": _fmt_ts(row_s["max_ts"] if row_s else None),
            "status": "Healthy" if (row_s and row_s["cnt"] > 0) else "Empty",
            "badge_color": "success" if (row_s and row_s["cnt"] > 0) else "secondary",
        },
        {
            "id": "analytics_fct_consumptions_daily",
            "name": "Daily Analytics Mart",
            "table": "analytics_fct_consumptions_daily",
            "description": "Consolidated daily consumption, costs, and standing charges",
            "count": row_a["cnt"] if row_a else 0,
            "earliest": _fmt_ts(row_a["min_ts"] if row_a else None),
            "latest": _fmt_ts(row_a["max_ts"] if row_a else None),
            "status": "Healthy" if (row_a and row_a["cnt"] > 0) else "Empty",
            "badge_color": "success" if (row_a and row_a["cnt"] > 0) else "secondary",
        },
    ]


def get_daily_availability(
    table: str = "source_consumptions",
    account_id: int | None = None,
    days_back: int = 365,
    end_date_str: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict:
    """Generate daily availability metrics for the GitHub-style tile calendar.

    Returns:
        dict with:
            - 'days': list of daily status dicts for the window
            - 'summary': high-level KPI metrics (total, complete, partial, missing, %)
            - 'start_date': YYYY-MM-DD
            - 'end_date': YYYY-MM-DD
    """
    today = datetime.date.today()
    if end_date_str:
        try:
            end_date = datetime.date.fromisoformat(end_date_str)
        except ValueError:
            end_date = today
    else:
        end_date = today

    start_date = end_date - datetime.timedelta(days=days_back - 1)

    # Pad start_date backwards to the preceding Monday so the calendar grid aligns cleanly
    grid_start_date = start_date - datetime.timedelta(days=start_date.weekday())

    # Build date counts from the database
    with _conn(conn) as c:
        if table == "source_consumptions":
            rows = c.execute(
                """
                SELECT date(interval_start) AS dt,
                       COUNT(*) AS cnt,
                       SUM(consumption_kwh) AS total_kwh
                FROM source_consumptions
                WHERE date(interval_start) >= ? AND date(interval_start) <= ?
                GROUP BY dt
                """,
                (grid_start_date.isoformat(), end_date.isoformat()),
            ).fetchall()
            db_map = {r["dt"]: {"count": r["cnt"], "kwh": r["total_kwh"] or 0.0} for r in rows}

        elif table in ("source_electricity_standard_unit_rates", "source_electricity_standing_charges"):
            # Check interval overlap
            rows = c.execute(
                f"""
                SELECT interval_start, interval_end
                FROM {table}
                """
            ).fetchall()
            # Mark each date as covered if an interval covers it
            db_map = {}
            for r in rows:
                r_start = r["interval_start"][:10]
                r_end = r["interval_end"][:10] if r["interval_end"] else end_date.isoformat()
                cur = max(datetime.date.fromisoformat(r_start), grid_start_date)
                stop = min(datetime.date.fromisoformat(r_end), end_date)
                while cur <= stop:
                    dt_str = cur.isoformat()
                    db_map[dt_str] = {"count": 48, "kwh": 0.0}
                    cur += datetime.timedelta(days=1)

        else:  # analytics_fct_consumptions_daily
            rows = c.execute(
                """
                SELECT date AS dt,
                       consumption_kwh AS kwh,
                       total_pence_inc_vat AS cost
                FROM analytics_fct_consumptions_daily
                WHERE date >= ? AND date <= ?
                """,
                (grid_start_date.isoformat(), end_date.isoformat()),
            ).fetchall()
            db_map = {r["dt"]: {"count": 48, "kwh": r["kwh"] or 0.0, "cost": r["cost"] or 0.0} for r in rows}

    # Generate complete day-by-day sequence
    days_list = []
    complete_count = 0
    partial_count = 0
    missing_count = 0
    total_tracked_days = 0
    total_readings = 0
    total_kwh = 0.0

    curr = grid_start_date
    week_index = 0

    while curr <= end_date:
        dt_str = curr.isoformat()
        is_in_range = curr >= start_date

        val = db_map.get(dt_str)
        count = val["count"] if val else 0
        kwh = val.get("kwh", 0.0) if val else 0.0
        cost = val.get("cost", None) if val else None

        if count >= 48:
            status = "complete"
            pct = 100.0
            if is_in_range:
                complete_count += 1
        elif count > 0:
            status = "partial"
            pct = round((count / 48) * 100, 1)
            if is_in_range:
                partial_count += 1
        else:
            status = "missing"
            pct = 0.0
            if is_in_range:
                missing_count += 1

        if is_in_range:
            total_tracked_days += 1
            total_readings += count
            total_kwh += kwh

        days_list.append({
            "date": dt_str,
            "weekday": curr.weekday(),  # 0=Mon, 6=Sun
            "week_index": week_index,
            "month_label": curr.strftime("%b") if curr.day <= 7 and curr.weekday() == 0 else "",
            "month": curr.month,
            "status": status,
            "count": count,
            "expected": 48,
            "pct": pct,
            "kwh": round(kwh, 2),
            "cost_pence": round(cost, 1) if cost is not None else None,
            "is_in_range": is_in_range,
        })

        if curr.weekday() == 6:
            week_index += 1
        curr += datetime.timedelta(days=1)

    completeness_pct = (
        round((complete_count / total_tracked_days) * 100, 1) if total_tracked_days > 0 else 0.0
    )

    # Get overall earliest/latest date in the table
    earliest_date = min((d["date"] for d in days_list if d["count"] > 0), default=None)
    latest_date = max((d["date"] for d in days_list if d["count"] > 0), default=None)

    summary = {
        "total_days": total_tracked_days,
        "complete_days": complete_count,
        "partial_days": partial_count,
        "missing_days": missing_count,
        "completeness_pct": completeness_pct,
        "total_readings": total_readings,
        "total_kwh": round(total_kwh, 1),
        "earliest_date": earliest_date,
        "latest_date": latest_date,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }

    return {
        "days": days_list,
        "summary": summary,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }


def run_chunked_backfill(
    account_id: int,
    start_date: str,
    end_date: str,
    chunk_days: int = 14,
    progress_cb: Optional[ProgressCb] = None,
) -> dict:
    """Execute historical backfill in chunked windows with progress streaming."""
    try:
        orchestrator.chunked_backfill(
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
            chunk_days=chunk_days,
            progress_cb=progress_cb,
        )
        return {"status": "COMPLETE", "error": None}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}
