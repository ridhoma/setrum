"""Callbacks for the Data Health tab — Option A: Editorial Ledger & Coverage Matrix.

Supports:
- 5-cell Editorial KPI strip
- Full-width CSS-Grid 52-week Coverage Matrix
- Interactive single-tile & multi-tile range selection on the matrix
- 1-click backfill directly from the matrix inspector bar OR from the Historical Backfill Workbench
"""

from __future__ import annotations

import datetime
import dash_bootstrap_components as dbc
from dash import ALL, Input, Output, State, callback, ctx, html, no_update

from core.services import data_health as health_service
from dash_app import stores


def _format_date_nice(dt_str: str) -> str:
    try:
        dt = datetime.date.fromisoformat(dt_str[:10])
        return dt.strftime("%a %d %b %Y")
    except Exception:
        return dt_str


def _render_github_calendar(
    days_list: list[dict],
    sel_start: str | None = None,
    sel_end: str | None = None,
) -> html.Div:
    """Builds a full-width responsive CSS-Grid coverage matrix with aligned month & weekday headers."""
    if not days_list:
        return html.Div("No data available for the selected range.", className="text-muted p-4 text-center")

    weeks_count = max(d["week_index"] for d in days_list) + 1

    # Find the starting week index for each month
    month_starts: list[tuple[int, str]] = []
    seen_ym: set[str] = set()
    for d in days_list:
        if not d["is_in_range"]:
            continue
        ym = d["date"][:7]
        if ym not in seen_ym:
            seen_ym.add(ym)
            try:
                m_name = datetime.date.fromisoformat(d["date"]).strftime("%b")
                month_starts.append((d["week_index"], m_name))
            except Exception:
                pass

    month_spans = [html.Span("")]
    for idx, (w_idx, m_name) in enumerate(month_starts):
        # Avoid crowding if the very first partial month is <2 weeks before the next month
        if idx == 0 and len(month_starts) > 1 and (month_starts[1][0] - w_idx) < 2:
            continue
        month_spans.append(
            html.Span(
                m_name,
                style={"gridColumn": f"{w_idx + 2} / span 3"},
            )
        )

    month_row = html.Div(
        month_spans,
        className="dh-heatmap-months",
        style={"gridTemplateColumns": f"42px repeat({weeks_count}, minmax(0, 1fr))"},
    )

    tiles = []
    for d in days_list:
        dt_str = d["date"]
        status = d["status"]
        count = d["count"]
        expected = d["expected"]
        kwh = d["kwh"]
        cost = d.get("cost_pence")
        dt_nice = _format_date_nice(dt_str)

        is_selected = bool(
            sel_start and sel_end and sel_start <= dt_str <= sel_end
        )

        tooltip_lines = [
            f"📅 {dt_nice}",
            f"Coverage: {count}/{expected} intervals ({d['pct']}%)",
        ]
        if kwh > 0:
            tooltip_lines.append(f"⚡ Energy: {kwh} kWh")
        if cost is not None:
            tooltip_lines.append(f"💷 Cost: £{cost/100:.2f}")
        tooltip_lines.append("Click to select day (click a 2nd tile to select range)")

        cls = f"dh-hm-cell dh-hm-cell--{status}"
        if is_selected:
            cls += " dh-hm-cell--selected"

        tiles.append(
            html.Div(
                className=cls,
                title="\n".join(tooltip_lines),
                id={"type": "health-tile", "date": dt_str},
                n_clicks=0,
                **{"data-date": dt_str},
            )
        )

    day_labels = html.Div(
        [
            html.Span("Mon"),
            html.Span(""),
            html.Span("Wed"),
            html.Span(""),
            html.Span("Fri"),
            html.Span(""),
            html.Span("Sun"),
        ],
        className="dh-heatmap-days",
    )

    grid_body = html.Div(
        [
            day_labels,
            html.Div(
                tiles,
                className="dh-heatmap-grid",
                style={"gridTemplateColumns": f"repeat({weeks_count}, minmax(0, 1fr))"},
            ),
        ],
        className="dh-heatmap-body",
    )

    return html.Div([month_row, grid_body], className="dh-matrix-wrap")


def _render_kpi_cards(summary: dict) -> html.Div:
    """Renders the 5-column Editorial KPI Strip matching Option A."""
    pct = summary.get("completeness_pct", 0.0)
    status_cls = "ok" if pct >= 95 else ("warn" if pct >= 50 else "err")
    status_text = "● Healthy" if pct >= 95 else ("● Partial" if pct >= 50 else "● Gaps")

    complete_days = summary.get("complete_days", 0)
    total_days = summary.get("total_days", 0)
    missing_days = summary.get("missing_days", 0)
    partial_days = summary.get("partial_days", 0)
    gap_total = missing_days + partial_days

    earliest = summary.get("earliest_date") or "—"
    latest = summary.get("latest_date") or "—"

    return html.Div(
        [
            html.Div(
                [
                    html.Div("Window Completeness", className="kpi-label"),
                    html.Div(f"{pct}%", className="kpi-value"),
                    html.Div(
                        [
                            html.Span(status_text, className=f"dh-status-pill dh-status-pill--{status_cls}"),
                            html.Span(f"{complete_days} of {total_days} days"),
                        ],
                        className="kpi-sub",
                    ),
                ],
                className="kpi-cell hero-green",
            ),
            html.Div(
                [
                    html.Div("Complete Days (48/48)", className="kpi-label"),
                    html.Div(
                        [
                            f"{complete_days} ",
                            html.Span("days", className="dh-kpi-unit"),
                        ],
                        className="kpi-value",
                    ),
                    html.Div("All 30-min settlement slots present", className="kpi-sub"),
                ],
                className="kpi-cell",
            ),
            html.Div(
                [
                    html.Div("Incomplete / Gaps", className="kpi-label"),
                    html.Div(
                        [
                            f"{gap_total} ",
                            html.Span("days", className="dh-kpi-unit"),
                        ],
                        className="kpi-value",
                        style={"color": "var(--setrum-orange)" if gap_total > 0 else "var(--setrum-ink-900)"},
                    ),
                    html.Div(f"{partial_days} partial • {missing_days} missing", className="kpi-sub"),
                ],
                className="kpi-cell",
            ),
            html.Div(
                [
                    html.Div("Stored Intervals", className="kpi-label"),
                    html.Div(f"{summary.get('total_readings', 0):,}", className="kpi-value"),
                    html.Div(f"{summary.get('total_kwh', 0):,.1f} kWh cumulative", className="kpi-sub"),
                ],
                className="kpi-cell",
            ),
            html.Div(
                [
                    html.Div("Telemetry Horizon", className="kpi-label"),
                    html.Div(f"{latest}", className="kpi-value", style={"fontSize": "21px"}),
                    html.Div(f"Earliest: {earliest}", className="kpi-sub"),
                ],
                className="kpi-cell",
            ),
        ],
        className="kpi-strip dh-kpi-strip-5",
    )


def _render_tables_overview_table(tables: list[dict]) -> html.Table:
    """Renders the Editorial SQLite Storage & Pipeline Ledger."""
    rows = []
    for t in tables:
        is_ok = t["count"] > 0
        pill_cls = "dh-status-pill dh-status-pill--ok" if is_ok else "dh-status-pill dh-status-pill--warn"
        pill_label = "● Materialized" if "analytics" in t["table"] and is_ok else (f"● {t['status']}" if is_ok else "○ Empty")
        rows.append(
            html.Tr(
                [
                    html.Td(
                        [
                            html.Div(t["name"], className="dh-table-title"),
                            html.Div(f"{t['table']} • {t['description']}", className="dh-table-sub"),
                        ]
                    ),
                    html.Td(
                        f"{t['count']:,}",
                        className="text-end fw-semibold",
                    ),
                    html.Td(
                        f"{t['earliest']} → {t['latest']}",
                        className="text-nowrap",
                    ),
                    html.Td(
                        html.Span(pill_label, className=pill_cls),
                        className="text-end",
                    ),
                ]
            )
        )

    return html.Table(
        [
            html.Thead(
                html.Tr(
                    [
                        html.Th("Table & Pipeline Stage"),
                        html.Th("Rows", className="text-end"),
                        html.Th("Coverage Span"),
                        html.Th("Health", className="text-end"),
                    ]
                )
            ),
            html.Tbody(rows),
        ],
        className="dh-ledger-table",
    )


def _format_duration(duration_ms: int | None) -> str:
    if duration_ms is None:
        return "—"
    if duration_ms < 1000:
        return f"{duration_ms} ms"
    return f"{duration_ms / 1000:.2f} s"


def _format_log_ts(ts_str: str | None) -> str:
    if not ts_str:
        return "—"
    try:
        dt = datetime.datetime.fromisoformat(str(ts_str).replace(" ", "T"))
        return dt.strftime("%d %b %Y %H:%M:%S")
    except Exception:
        return str(ts_str)[:19]


def _render_process_run_logs(logs_data: dict) -> tuple[html.Component, str]:
    """Renders the Backend Process & Pipeline Run Log table and retention badge text."""
    logs = logs_data.get("logs", [])
    summary = logs_data.get("summary", {})
    total_retained = summary.get("total_retained", 0)
    filtered_count = summary.get("filtered_count", 0)
    retention_limit = summary.get("retention_limit", 100)

    if filtered_count != total_retained:
        badge_text = f"Showing {filtered_count} of {total_retained} / {retention_limit} max retained"
    else:
        badge_text = f"{total_retained} / {retention_limit} runs retained"

    if not logs:
        empty_div = html.Div(
            "No backend process runs recorded matching this filter yet.",
            className="text-muted p-4 text-center font-monospace small",
        )
        return empty_div, badge_text

    rows = []
    for item in logs:
        raw_status = (item.get("status") or "UNKNOWN").upper()
        if raw_status in ("SUCCESS", "COMPLETE"):
            pill_cls = "dh-status-pill dh-status-pill--ok"
            pill_label = "● Success"
        elif raw_status == "SKIPPED":
            pill_cls = "dh-status-pill dh-status-pill--neutral"
            pill_label = "○ Up to date"
        elif raw_status == "RUNNING":
            pill_cls = "dh-status-pill dh-status-pill--warn"
            pill_label = "↻ Running"
        else:
            pill_cls = "dh-status-pill dh-status-pill--err"
            pill_label = "✕ Error"

        cat_key = item.get("category_key", "orchestrator")
        cat_badge = item.get("category_badge", "SYSTEM")
        ts_display = _format_log_ts(item.get("finished_at") or item.get("started_at"))
        trigger_src = item.get("trigger_source") or "System"
        run_id = item.get("run_id") or ""
        sub_meta = f"{trigger_src} • {run_id}" if run_id else trigger_src

        ep_name = item.get("endpoint_name") or ""
        target_tbl = item.get("target_table") or ""
        ep_sub = f"{ep_name} → {target_tbl}" if target_tbl else ep_name

        rows_affected = item.get("rows_affected") or 0
        rows_str = f"{rows_affected:,}" if rows_affected > 0 else "—"
        dur_str = _format_duration(item.get("duration_ms"))
        details_str = item.get("details") or "—"
        is_err = raw_status.startswith("ERROR")

        rows.append(
            html.Tr(
                [
                    html.Td(
                        [
                            html.Div(ts_display, className="dh-log-ts"),
                            html.Div(sub_meta, className="dh-table-sub"),
                        ],
                        className="text-nowrap",
                    ),
                    html.Td(
                        [
                            html.Div(
                                [
                                    html.Span(
                                        cat_badge,
                                        className=f"dh-proc-badge dh-proc-badge--{cat_key}",
                                    ),
                                    html.Span(item.get("title", ep_name), className="dh-table-title"),
                                ],
                                className="d-flex align-items-center gap-2 flex-wrap",
                            ),
                            html.Div(ep_sub, className="dh-table-sub text-truncate", style={"maxWidth": "340px"}, title=ep_sub),
                        ]
                    ),
                    html.Td(
                        html.Div(
                            details_str,
                            className="dh-log-details" + (" dh-log-details--err" if is_err else ""),
                        )
                    ),
                    html.Td(
                        rows_str,
                        className="text-end fw-semibold text-nowrap",
                    ),
                    html.Td(
                        dur_str,
                        className="text-end text-muted text-nowrap",
                    ),
                    html.Td(
                        html.Span(pill_label, className=pill_cls),
                        className="text-end text-nowrap",
                    ),
                ],
                className="dh-log-row--err" if is_err else "",
            )
        )

    table = html.Table(
        [
            html.Thead(
                html.Tr(
                    [
                        html.Th("Timestamp (UTC)"),
                        html.Th("Backend Process & Target"),
                        html.Th("Execution Log / Window"),
                        html.Th("Records", className="text-end"),
                        html.Th("Duration", className="text-end"),
                        html.Th("Status", className="text-end"),
                    ]
                )
            ),
            html.Tbody(rows),
        ],
        className="dh-ledger-table dh-process-log-table",
    )
    return table, badge_text


def _render_selection_inspector(
    days_list: list[dict],
    sel_start: str | None,
    sel_end: str | None,
) -> tuple[list, list, str, dict]:
    """Build the summary text, mini visual strip, backfill button label, and clear button style."""
    if not days_list:
        return [html.Span("No telemetry in window")], [], "↻ Backfill", {"display": "none"}

    by_date = {d["date"]: d for d in days_list}

    # If user hasn't clicked a tile yet, highlight the latest date with data (or latest date in window)
    active_user_selection = bool(sel_start and sel_end)
    if not active_user_selection:
        in_range_days = [d for d in days_list if d["is_in_range"]]
        default_day = in_range_days[-1]["date"] if in_range_days else days_list[-1]["date"]
        s_date = e_date = default_day
    else:
        s_date, e_date = sel_start, sel_end

    if s_date == e_date:
        info = by_date.get(s_date, {"count": 0, "expected": 48, "kwh": 0.0})
        slots_24 = health_service.get_intraday_slots(s_date)
        strip = [
            html.Div(
                className="dh-mini-slot" + ("" if ok else " dh-mini-slot--gap"),
                title=f"{h:02d}:00–{h:02d}:59 ({'Complete' if ok else 'Missing/Partial'})",
            )
            for h, ok in enumerate(slots_24)
        ]
        prefix = "Selected: " if active_user_selection else "Latest Day: "
        summary = [
            html.Strong(f"{prefix}{_format_date_nice(s_date)}"),
            f" • {info['count']}/{info['expected']} slots ({info['kwh']:.1f} kWh)",
        ]
        btn_label = f"↻ Backfill Day ({s_date})"
        clear_style = {"display": "inline-flex"} if active_user_selection else {"display": "none"}
        return summary, strip, btn_label, clear_style

    # Multi-day range selected
    range_days = [d for d in days_list if s_date <= d["date"] <= e_date]
    n_days = len(range_days)
    total_slots = sum(d["count"] for d in range_days)
    expected_slots = n_days * 48
    total_kwh = sum(d["kwh"] for d in range_days)

    # Show up to 24 mini bars representing days in the selected range
    sample = range_days[:24]
    strip = [
        html.Div(
            className="dh-mini-slot" + ("" if d["status"] == "complete" else " dh-mini-slot--gap"),
            title=f"{d['date']}: {d['count']}/48 slots",
        )
        for d in sample
    ]
    summary = [
        html.Strong(f"Selected Range: {s_date} → {e_date}"),
        f" ({n_days}d • {total_slots:,}/{expected_slots:,} slots • {total_kwh:.1f} kWh)",
    ]
    btn_label = f"↻ Backfill Range ({n_days}d) →"
    return summary, strip, btn_label, {"display": "inline-flex"}


@callback(
    output=[
        Output("health-tile-selection", "data"),
        Output("backfill-date-picker", "start_date"),
        Output("backfill-date-picker", "end_date"),
    ],
    inputs=[
        Input({"type": "health-tile", "date": ALL}, "n_clicks"),
        Input("matrix-clear-btn", "n_clicks"),
        Input("backfill-preset-30d", "n_clicks"),
        Input("backfill-preset-90d", "n_clicks"),
        Input("backfill-preset-ytd", "n_clicks"),
        Input("backfill-preset-movein", "n_clicks"),
        Input("health-account-select", "value"),
    ],
    state=State("health-tile-selection", "data"),
    prevent_initial_call=True,
)
def handle_tile_and_preset_selection(
    tile_clicks,
    _clear_clicks,
    _n30,
    _n90,
    _nytd,
    _nmovein,
    account_id: int | None,
    current_sel: dict | None,
):
    triggered = ctx.triggered_id
    today = datetime.date.today()

    if triggered == "matrix-clear-btn":
        return None, no_update, no_update

    if isinstance(triggered, dict) and triggered.get("type") == "health-tile":
        # Guard against spurious initial 0-click triggers when grid re-renders
        if not any(c and c > 0 for c in (tile_clicks or [])):
            return no_update, no_update, no_update
        clicked_date = triggered.get("date")
        if not clicked_date:
            return no_update, no_update, no_update

        anchor = (current_sel or {}).get("anchor")
        if anchor and anchor != clicked_date:
            s_d = min(anchor, clicked_date)
            e_d = max(anchor, clicked_date)
            new_sel = {"start_date": s_d, "end_date": e_d, "anchor": None}
            return new_sel, s_d, e_d

        new_sel = {"start_date": clicked_date, "end_date": clicked_date, "anchor": clicked_date}
        return new_sel, clicked_date, clicked_date

    if triggered == "backfill-preset-30d":
        s_d = (today - datetime.timedelta(days=30)).isoformat()
        e_d = today.isoformat()
        return {"start_date": s_d, "end_date": e_d, "anchor": None}, s_d, e_d

    if triggered == "backfill-preset-90d":
        s_d = (today - datetime.timedelta(days=90)).isoformat()
        e_d = today.isoformat()
        return {"start_date": s_d, "end_date": e_d, "anchor": None}, s_d, e_d

    if triggered == "backfill-preset-ytd":
        s_d = datetime.date(today.year, 1, 1).isoformat()
        e_d = today.isoformat()
        return {"start_date": s_d, "end_date": e_d, "anchor": None}, s_d, e_d

    if triggered in ("backfill-preset-movein", "health-account-select"):
        accounts = health_service.get_accounts()
        target = next((a for a in accounts if a["account_id"] == account_id), None)
        if target and target.get("moved_in_at"):
            try:
                s_d = datetime.date.fromisoformat(target["moved_in_at"][:10]).isoformat()
                e_d = (
                    datetime.date.fromisoformat(target["moved_out_at"][:10]).isoformat()
                    if target.get("moved_out_at")
                    else today.isoformat()
                )
                sel = {"start_date": s_d, "end_date": e_d, "anchor": None} if triggered == "backfill-preset-movein" else None
                return sel, s_d, e_d
            except Exception:
                pass
        s_d = (today - datetime.timedelta(days=90)).isoformat()
        e_d = today.isoformat()
        return None, s_d, e_d

    return no_update, no_update, no_update


@callback(
    output=[
        Output("health-kpi-container", "children"),
        Output("health-calendar-grid", "children"),
        Output("health-tables-overview-container", "children"),
        Output("health-selection-summary", "children"),
        Output("health-selection-strip", "children"),
        Output("matrix-backfill-btn", "children"),
        Output("matrix-clear-btn", "style"),
    ],
    inputs=[
        Input(stores.DATA_VERSION, "data"),
        Input("health-account-select", "value"),
        Input("health-table-select", "value"),
        Input("health-window-select", "value"),
        Input("health-tile-selection", "data"),
    ],
)
def update_health_view(
    _data_version: int,
    account_id: int | None,
    table_name: str | None,
    window_days: int | None,
    tile_sel: dict | None,
):
    table = table_name or "source_consumptions"
    days = window_days or 365

    availability = health_service.get_daily_availability(
        table=table,
        account_id=account_id,
        days_back=days,
    )
    tables_overview = health_service.get_raw_tables_overview(account_id=account_id)

    sel_start = (tile_sel or {}).get("start_date")
    sel_end = (tile_sel or {}).get("end_date")

    kpi_cards = _render_kpi_cards(availability["summary"])
    calendar_grid = _render_github_calendar(availability["days"], sel_start=sel_start, sel_end=sel_end)
    tables_table = _render_tables_overview_table(tables_overview)
    sel_summary, sel_strip, btn_label, clear_style = _render_selection_inspector(
        availability["days"], sel_start, sel_end
    )

    return (
        kpi_cards,
        calendar_grid,
        tables_table,
        sel_summary,
        sel_strip,
        btn_label,
        clear_style,
    )


@callback(
    output=[
        Output(stores.DATA_VERSION, "data", allow_duplicate=True),
        Output("backfill-status-alert", "children"),
        Output("backfill-progress-label", "children"),
        Output("backfill-progress-bar", "value"),
    ],
    inputs=[
        Input("backfill-start-btn", "n_clicks"),
        Input("matrix-backfill-btn", "n_clicks"),
    ],
    state=[
        State("health-account-select", "value"),
        State("backfill-date-picker", "start_date"),
        State("backfill-date-picker", "end_date"),
        State("health-tile-selection", "data"),
        State("backfill-chunk-size", "value"),
        State(stores.DATA_VERSION, "data"),
    ],
    background=True,
    running=[
        (Output("backfill-start-btn", "disabled"), True, False),
        (Output("matrix-backfill-btn", "disabled"), True, False),
        (
            Output("backfill-start-btn", "children"),
            "Backfilling in progress…",
            "↻ Run Chunked Backfill & Rebuild Marts",
        ),
        (Output("backfill-progress-bar", "style"), {"display": "flex"}, {"display": "none"}),
    ],
    progress=[
        Output("backfill-progress-bar", "value"),
        Output("backfill-progress-bar", "max"),
        Output("backfill-progress-label", "children"),
    ],
    prevent_initial_call=True,
)
def on_start_backfill(
    set_progress,
    n_workbench: int | None,
    n_matrix: int | None,
    account_id: int | None,
    start_date: str | None,
    end_date: str | None,
    tile_sel: dict | None,
    chunk_size: int | None,
    current_version: int | None,
):
    if not (n_workbench or n_matrix) or not account_id:
        return current_version or 0, no_update, "", 0

    # If triggered from the matrix inspector bar and a tile selection exists, use it;
    # otherwise use the workbench date picker (or today if neither is set).
    if tile_sel and tile_sel.get("start_date") and tile_sel.get("end_date"):
        s_date = tile_sel["start_date"]
        e_date = tile_sel["end_date"]
    else:
        today_iso = datetime.date.today().isoformat()
        s_date = start_date or today_iso
        e_date = end_date or today_iso

    chunks = chunk_size or 14

    def cb(step: str, current: int, total: int) -> None:
        max_val = total if total else 1
        label = f"{step} ({current}/{max_val})"
        set_progress((current, max_val, label))

    res = health_service.run_chunked_backfill(
        account_id=account_id,
        start_date=s_date,
        end_date=e_date,
        chunk_days=chunks,
        progress_cb=cb,
    )

    new_version = (current_version or 0) + 1

    if res["status"] == "COMPLETE":
        alert = dbc.Alert(
            [
                html.Span("✅ ", className="me-1"),
                html.Strong("Backfill Complete! "),
                f"Historical data from {s_date} to {e_date} downloaded and materialized.",
            ],
            color="success",
            dismissable=True,
            className="mb-0 mt-2",
        )
    else:
        alert = dbc.Alert(
            [
                html.Span("❌ ", className="me-1"),
                html.Strong("Backfill Error: "),
                str(res.get("error", "Unknown error")),
            ],
            color="danger",
            dismissable=True,
            className="mb-0 mt-2",
        )

    return new_version, alert, "", 0


@callback(
    output=[
        Output("health-process-logs-container", "children"),
        Output("health-log-retention-badge", "children"),
    ],
    inputs=[
        Input(stores.DATA_VERSION, "data"),
        Input("health-log-filter-select", "value"),
        Input("health-log-refresh-btn", "n_clicks"),
        Input("sync-poll-interval", "n_intervals"),
    ],
)
def update_process_run_logs(
    _data_version: int | None,
    category: str | None,
    _refresh_clicks: int | None,
    _poll_intervals: int | None,
):
    logs_data = health_service.get_process_run_logs(category=category or "all", limit=100)
    return _render_process_run_logs(logs_data)
