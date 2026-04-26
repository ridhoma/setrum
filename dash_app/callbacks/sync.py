"""Refresh button (background callback).

Runs `services.sync.run_sync` in a worker process backed by diskcache,
streaming progress back through Dash's `set_progress` mechanism. The
button is disabled and relabeled while a sync is in flight; when it
finishes, DATA_VERSION bumps so every chart callback re-fetches.

`prevent_initial_call=True` is critical — without it, every page load
would kick off a full Octopus sync.
"""

from __future__ import annotations

from dash import Input, Output, State, callback

from core.services import sync as sync_service
from dash_app import stores


@callback(
    output=[
        Output(stores.DATA_VERSION, "data"),
        Output("sync-progress-label", "children"),
        Output("sync-progress-bar",   "value"),
    ],
    inputs=Input("refresh-btn", "n_clicks"),
    state=State(stores.DATA_VERSION, "data"),
    background=True,
    running=[
        (Output("refresh-btn", "disabled"),  True,  False),
        (Output("refresh-btn", "children"),  "Syncing…", "Refresh"),
        (Output("sync-progress-bar", "style"),
         {"display": "block"}, {"display": "none"}),
    ],
    progress=[
        Output("sync-progress-bar", "value"),
        Output("sync-progress-bar", "max"),
        Output("sync-progress-label", "children"),
    ],
    prevent_initial_call=True,
)
def on_refresh(set_progress, n_clicks: int | None, current_version: int | None):
    if not n_clicks:
        return current_version or 0, "", 0

    def cb(step: str, current: int, total: int) -> None:
        # Some steps run before we know `total` (e.g. accounts) — fall back
        # to a 1-step bar so the visual still progresses.
        max_val = total if total else 1
        cur_val = current
        label = f"Syncing {step} ({current}/{max_val})…"
        set_progress((cur_val, max_val, label))

    sync_service.run_sync(progress_cb=cb)
    # On completion, wipe the progress label/bar so the sidebar doesn't keep
    # showing the last in-flight step (e.g. "Syncing transform (1/1)…").
    return (current_version or 0) + 1, "", 0


def _humanize_delta(then_iso: str | None) -> str:
    """Render a 'N minutes/hours/days ago' string from a UTC ISO timestamp.

    SQLite's `datetime('now')` writes naive UTC strings (`YYYY-MM-DD HH:MM:SS`),
    so we treat any tz-naive value as UTC.
    """
    import datetime as _dt

    if not then_iso:
        return "never"
    try:
        then = _dt.datetime.fromisoformat(str(then_iso).replace(" ", "T"))
    except ValueError:
        return then_iso
    if then.tzinfo is None:
        then = then.replace(tzinfo=_dt.timezone.utc)
    delta = _dt.datetime.now(_dt.timezone.utc) - then
    secs = int(delta.total_seconds())
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{secs // 60} min ago"
    if secs < 86400:
        return f"{secs // 3600} h ago"
    return f"{secs // 86400} d ago"


@callback(
    Output("sync-status-pill", "children"),
    Input(stores.DATA_VERSION, "data"),
    Input(stores.ACTIVE_ACCOUNT_ID, "data"),
)
def render_status_pill(_dv: int, account_id: int | None):
    """Pill summarises *data freshness* and *last sync time* separately.

    Octopus consumption data lags ~1 day, so a successful sync today still
    yields data ending yesterday — the pill must distinguish 'I just synced'
    from 'the data is up to date'.
    """
    import dash_bootstrap_components as dbc
    from dash import html

    from core.services import consumption as consumption_service

    status = sync_service.get_sync_status()
    s = status.get("status")
    last_run = status.get("last_run_at")
    err = status.get("error_message")

    extent = consumption_service.get_data_extent(account_id=account_id)
    latest = extent.get("hh_max")

    if s == "RUNNING":
        return dbc.Badge("🔄 Syncing…", color="info", className="me-2")

    if s == "ERROR":
        return dbc.Badge(
            f"❌ Sync failed: {err or 'unknown'} (last try {_humanize_delta(last_run)})",
            color="danger",
            className="me-2",
        )

    if s in (None, "NEVER_RUN"):
        return dbc.Badge("⚠️ Never synced — click Refresh", color="warning", className="me-2")

    # Successful (or at least non-error) sync. Decide colour by staleness.
    is_stale = bool(status.get("is_stale"))
    color = "warning" if is_stale else "success"
    icon = "⚠️" if is_stale else "✅"
    latest_label = latest if latest else "no data yet"
    last_run_label = _humanize_delta(last_run)

    return html.Span(
        [
            dbc.Badge(
                f"{icon} Latest data: {latest_label}",
                color=color,
                className="me-2",
            ),
            html.Small(f"Synced {last_run_label}", className="text-muted"),
        ]
    )
