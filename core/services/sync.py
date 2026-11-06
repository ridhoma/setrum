"""Sync orchestration façade for the UI layer.

Wraps `core.orchestrator.auto_catch_up` so the UI never imports the
orchestrator or queries directly. Threads a progress callback through
and surfaces a structured result + status reads from `job_runs`.
"""

from __future__ import annotations

import datetime
import logging
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Callable, Iterator, Optional

import pandas as pd

from core import orchestrator
from core.database import get_connection

logger = logging.getLogger(__name__)

ProgressCb = Callable[[str, int, int], None]

DEFAULT_SYNC_INTERVAL_HOURS = float(os.environ.get("SETRUM_SYNC_INTERVAL_HOURS", "6"))
_sync_lock = threading.Lock()
_scheduler_started = False


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


def _is_actively_running(max_age_minutes: int = 5) -> bool:
    """Return True if a sync job is currently marked RUNNING and started recently."""
    with _conn(None) as c:
        row = c.execute(
            "SELECT status, last_run_at FROM job_runs WHERE endpoint_name = ?",
            (orchestrator.SYNC_JOB_NAME,),
        ).fetchone()
    if not row or row["status"] != "RUNNING":
        return False
    last_run_at = row["last_run_at"]
    if not last_run_at:
        return False
    try:
        last = datetime.datetime.fromisoformat(str(last_run_at).replace(" ", "T"))
        if last.tzinfo is None:
            last = last.replace(tzinfo=datetime.timezone.utc)
        age = datetime.datetime.now(datetime.timezone.utc) - last
        return age < datetime.timedelta(minutes=max_age_minutes)
    except ValueError:
        return False


def run_sync(progress_cb: Optional[ProgressCb] = None) -> dict:
    """Run a forward-fill sync.

    Returns `{"status": "COMPLETE" | "ERROR", "error": str | None}`. Never
    raises — UI callbacks expect to display the outcome regardless.
    If another thread/worker is already running a sync, waits for it to finish.
    """
    if _is_actively_running():
        for _ in range(120):
            if not _is_actively_running():
                return {"status": "COMPLETE", "error": None}
            time.sleep(0.5)

    with _sync_lock:
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
    out["is_stale"] = _is_stale(out.get("last_run_at")) or out.get("status") == "ERROR"
    return out


def _is_stale(last_run_at: str | None, hours: float = DEFAULT_SYNC_INTERVAL_HOURS) -> bool:
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


def start_background_scheduler(
    interval_hours: float = DEFAULT_SYNC_INTERVAL_HOURS,
    run_on_startup: bool = True,
) -> None:
    """Start a background daemon thread that syncs on app startup/reset and every `interval_hours`."""
    global _scheduler_started
    if _scheduler_started:
        return
    # Avoid starting duplicate threads in the outer Werkzeug reloader watcher process
    if os.environ.get("WERKZEUG_RUN_MAIN") == "false":
        return
    _scheduler_started = True

    interval_secs = max(60.0, float(interval_hours) * 3600.0)

    def _loop() -> None:
        if run_on_startup:
            logger.info("Auto-sync scheduler: running initial sync on app startup...")
            res = run_sync()
            logger.info("Auto-sync scheduler: startup sync finished (%s)", res.get("status"))
        while True:
            time.sleep(interval_secs)
            logger.info("Auto-sync scheduler: running periodic %.1fh sync...", interval_hours)
            res = run_sync()
            logger.info("Auto-sync scheduler: periodic sync finished (%s)", res.get("status"))

    t = threading.Thread(target=_loop, name="setrum-auto-sync", daemon=True)
    t.start()


def get_job_runs(conn: sqlite3.Connection | None = None) -> pd.DataFrame:
    """All job_runs rows — used by status panels and debug views."""
    with _conn(conn) as c:
        return pd.read_sql_query(
            "SELECT * FROM job_runs ORDER BY last_run_at DESC", c
        )
