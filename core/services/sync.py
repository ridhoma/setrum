"""Sync orchestration façade for the UI layer.

Wraps `core.orchestrator.auto_catch_up` so the UI never imports the
orchestrator or queries directly. Threads a progress callback through
and surfaces a structured result + status reads from `job_runs`.
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


def run_sync(progress_cb: Optional[ProgressCb] = None) -> dict:
    """Run a forward-fill sync.

    Returns `{"status": "COMPLETE" | "ERROR", "error": str | None}`. Never
    raises — UI callbacks expect to display the outcome regardless.
    """
    try:
        orchestrator.auto_catch_up(progress_cb=progress_cb)
        return {"status": "COMPLETE", "error": None}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


def get_sync_status(conn: sqlite3.Connection | None = None) -> dict:
    """Surface the latest `_sync` job_runs row plus a derived staleness flag."""
    with _conn(conn) as c:
        row = c.execute(
            "SELECT * FROM job_runs WHERE endpoint_name = ?",
            (orchestrator.SYNC_JOB_NAME,),
        ).fetchone()
    if row is None:
        return {
            "status": "NEVER_RUN",
            "last_run_at": None,
            "last_successful_timestamp": None,
            "error_message": None,
            "is_stale": True,
        }
    out = dict(row)
    out["is_stale"] = _is_stale(out.get("last_run_at"))
    return out


def _is_stale(last_run_at: str | None, hours: int = 1) -> bool:
    if not last_run_at:
        return True
    try:
        last = datetime.datetime.fromisoformat(last_run_at.replace(" ", "T"))
    except ValueError:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=datetime.timezone.utc)
    delta = datetime.datetime.now(datetime.timezone.utc) - last
    return delta > datetime.timedelta(hours=hours)


def get_job_runs(conn: sqlite3.Connection | None = None) -> pd.DataFrame:
    """All job_runs rows — used by status panels and debug views."""
    with _conn(conn) as c:
        return pd.read_sql_query(
            "SELECT * FROM job_runs ORDER BY last_run_at DESC", c
        )
