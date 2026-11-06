"""Callbacks for the Data Health tab: tile heatmap, audit table, and chunked backfill."""

from __future__ import annotations

import datetime
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, ctx, html, no_update

from core.services import data_health as health_service
from dash_app import stores


def _format_date_nice(dt_str: str) -> str:
    try:
        dt = datetime.date.fromisoformat(dt_str)
        return dt.strftime("%a, %b %d, %Y")
    except Exception:
        return dt_str


def _render_github_calendar(days_list: list[dict], summary: dict) -> html.Div:
    """Builds a GitHub contribution-style grid with month labels and day rows."""
    if not days_list:
        return html.Div("No data available for the selected range.", className="text-muted p-4 text-center")

    # Group by week_index to find month headers
    month_headers = []
    seen_months = set()
    current_week = 0

    # Collect month markers per week
    weeks_count = max(d["week_index"] for d in days_list) + 1
    week_months = [""] * weeks_count

    for d in days_list:
        w_idx = d["week_index"]
        m_label = d["date"][5:7]  # MM
        if m_label not in seen_months and d["is_in_range"]:
            seen_months.add(m_label)
            try:
                m_name = datetime.date.fromisoformat(d["date"]).strftime("%b")
                week_months[w_idx] = m_name
            except Exception:
                pass

    # Build tiles
    tiles = []
    for d in days_list:
        status = d["status"]
        count = d["count"]
        expected = d["expected"]
        kwh = d["kwh"]
        cost = d.get("cost_pence")
        dt_nice = _format_date_nice(d["date"])

        tooltip_lines = [
            f"📅 {dt_nice}",
            f"Coverage: {count}/{expected} intervals ({d['pct']}%)",
        ]
        if kwh > 0:
            tooltip_lines.append(f"⚡ Energy: {kwh} kWh")
        if cost is not None:
            tooltip_lines.append(f"💷 Cost: {cost/100:.2f}")

        tooltip_text = "\n".join(tooltip_lines)

        tiles.append(
            html.Div(
                className=f"health-tile health-tile--{status}",
                title=tooltip_text,
                id={"type": "health-tile", "date": d["date"]},
            )
        )

    # Days of week labels on the left (7 rows)
    day_labels = html.Div(
        [
            html.Div("Mon"),
            html.Div(""),
            html.Div("Wed"),
            html.Div(""),
            html.Div("Fri"),
            html.Div(""),
            html.Div(""),
        ],
        className="health-day-labels",
    )

    # Month header row above the grid
    # Each column in grid is 11px + 2.5px gap = 13.5px wide
    month_spans = []
    for w_idx, m_name in enumerate(week_months):
        if m_name:
            left_pos = int(w_idx * 13.5)
            month_spans.append(
                html.Span(
                    m_name,
                    style={
                        "position": "absolute",
                        "left": f"{left_pos + 32}px",
                        "whiteSpace": "nowrap",
                    },
                )
            )

    month_row = html.Div(month_spans, className="health-month-labels")

    grid_body = html.Div(
        [
            day_labels,
            html.Div(tiles, className="health-tiles-grid"),
        ],
        className="health-calendar-body",
    )

    return html.Div(
        html.Div(
            [month_row, grid_body],
            className="health-calendar-grid-wrapper",
        ),
        className="health-calendar-scroll",
    )


def _render_kpi_cards(summary: dict) -> dbc.Row:
    """Renders high-level summary cards."""
    pct = summary.get("completeness_pct", 0.0)
    badge_color = "success" if pct >= 95 else ("warning" if pct >= 50 else "danger")
    badge_text = "Healthy" if pct >= 95 else ("Partial" if pct >= 50 else "Gaps Detected")

    earliest = summary.get("earliest_date") or "—"
    latest = summary.get("latest_date") or "—"

    return html.Div(
        [
            html.Div(
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.Div("Completeness", className="summary-label"),
                            html.H5(f"{pct}%", className="mb-1"),
                            html.Div(
                                [
                                    dbc.Badge(badge_text, color=badge_color, className="me-2"),
                                    html.Small(f"{summary.get('complete_days', 0)} of {summary.get('total_days', 0)} days", className="text-muted"),
                                ],
                                className="d-flex align-items-center mt-1",
                            ),
                        ]
                    ),
                    className="summary-card h-100",
                ),
                className="col",
            ),
            html.Div(
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.Div("Complete Days", className="summary-label"),
                            html.H5(f"{summary.get('complete_days', 0)} days", className="text-success"),
                            html.Small("48/48 half-hour slots", className="text-muted d-block mt-1"),
                        ]
                    ),
                    className="summary-card h-100",
                ),
                className="col",
            ),
            html.Div(
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.Div("Missing Days", className="summary-label"),
                            html.H5(
                                f"{summary.get('missing_days', 0)} days",
                                className="text-danger" if summary.get("missing_days", 0) > 0 else "text-muted",
                            ),
                            html.Small(
                                f"{summary.get('partial_days', 0)} partial days",
                                className="text-muted d-block mt-1",
                            ),
                        ]
                    ),
                    className="summary-card h-100",
                ),
                className="col",
            ),
            html.Div(
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.Div("Telemetry Points", className="summary-label"),
                            html.H5(f"{summary.get('total_readings', 0):,}"),
                            html.Small(f"{summary.get('total_kwh', 0):,.1f} kWh", className="text-muted d-block mt-1"),
                        ]
                    ),
                    className="summary-card h-100",
                ),
                className="col",
            ),
            html.Div(
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.Div("Latest Telemetry", className="summary-label"),
                            html.H5(f"{latest}"),
                            html.Small(f"From {earliest}", className="text-muted d-block mt-1"),
                        ]
                    ),
                    className="summary-card h-100",
                ),
                className="col",
            ),
        ],
        className="row row-cols-2 row-cols-md-3 row-cols-lg-5 g-3",
    )


def _render_tables_overview_table(tables: list[dict]) -> html.Div:
    """Renders the table audit overview."""
    rows = []
    for t in tables:
        rows.append(
            html.Tr(
                [
                    html.Td(
                        [
                            html.Div(t["name"], className="fw-semibold"),
                            html.Small(t["description"], className="text-muted font-monospace"),
                        ]
                    ),
                    html.Td(
                        f"{t['count']:,}",
                        className="font-monospace text-end",
                    ),
                    html.Td(
                        html.Small(f"{t['earliest']} → {t['latest']}", className="font-monospace text-muted"),
                        className="text-nowrap",
                    ),
                    html.Td(
                        dbc.Badge(t["status"], color=t["badge_color"], className="px-2 py-1"),
                        className="text-center",
                    ),
                ]
            )
        )

    table = dbc.Table(
        [
            html.Thead(
                html.Tr(
                    [
                        html.Th("Data Source & Description"),
                        html.Th("Rows", className="text-end"),
                        html.Th("Coverage Span"),
                        html.Th("Status", className="text-center"),
                    ]
                )
            ),
            html.Tbody(rows),
        ],
        hover=True,
        responsive=True,
        className="mb-0",
    )
    return html.Div(table)


@callback(
    output=[
        Output("health-kpi-container", "children"),
        Output("health-calendar-grid", "children"),
        Output("health-tables-overview-container", "children"),
    ],
    inputs=[
        Input(stores.DATA_VERSION, "data"),
        Input("health-account-select", "value"),
        Input("health-table-select", "value"),
        Input("health-window-select", "value"),
    ],
)
def update_health_view(_data_version: int, account_id: int | None, table_name: str | None, window_days: int | None):
    table = table_name or "source_consumptions"
    days = window_days or 365

    availability = health_service.get_daily_availability(
        table=table,
        account_id=account_id,
        days_back=days,
    )
    tables_overview = health_service.get_raw_tables_overview(account_id=account_id)

    kpi_cards = _render_kpi_cards(availability["summary"])
    calendar_grid = _render_github_calendar(availability["days"], availability["summary"])
    tables_table = _render_tables_overview_table(tables_overview)

    return kpi_cards, calendar_grid, tables_table


@callback(
    output=[
        Output("backfill-date-picker", "start_date"),
        Output("backfill-date-picker", "end_date"),
    ],
    inputs=[
        Input("backfill-preset-30d", "n_clicks"),
        Input("backfill-preset-90d", "n_clicks"),
        Input("backfill-preset-ytd", "n_clicks"),
        Input("backfill-preset-movein", "n_clicks"),
        Input("health-account-select", "value"),
    ],
    prevent_initial_call=True,
)
def handle_backfill_presets(n30, n90, nytd, nmovein, account_id: int | None):
    triggered_id = ctx.triggered_id
    today = datetime.date.today()

    if triggered_id == "backfill-preset-30d":
        start = today - datetime.timedelta(days=30)
        return start.isoformat(), today.isoformat()

    if triggered_id == "backfill-preset-90d":
        start = today - datetime.timedelta(days=90)
        return start.isoformat(), today.isoformat()

    if triggered_id == "backfill-preset-ytd":
        start = datetime.date(today.year, 1, 1)
        return start.isoformat(), today.isoformat()

    if triggered_id in ("backfill-preset-movein", "health-account-select"):
        accounts = health_service.get_accounts()
        target = next((a for a in accounts if a["account_id"] == account_id), None)
        if target and target.get("moved_in_at"):
            try:
                start = datetime.date.fromisoformat(target["moved_in_at"][:10])
                end = datetime.date.fromisoformat(target["moved_out_at"][:10]) if target.get("moved_out_at") else today
                return start.isoformat(), end.isoformat()
            except Exception:
                pass
        # Fallback to 90 days
        start = today - datetime.timedelta(days=90)
        return start.isoformat(), today.isoformat()

    return no_update, no_update


@callback(
    output=[
        Output(stores.DATA_VERSION, "data", allow_duplicate=True),
        Output("backfill-status-alert", "children"),
        Output("backfill-progress-label", "children"),
        Output("backfill-progress-bar", "value"),
    ],
    inputs=Input("backfill-start-btn", "n_clicks"),
    state=[
        State("health-account-select", "value"),
        State("backfill-date-picker", "start_date"),
        State("backfill-date-picker", "end_date"),
        State("backfill-chunk-size", "value"),
        State(stores.DATA_VERSION, "data"),
    ],
    background=True,
    running=[
        (Output("backfill-start-btn", "disabled"), True, False),
        (Output("backfill-start-btn", "children"), "Backfilling in progress...", "🚀 Start Chunked Backfill"),
        (Output("backfill-progress-bar", "style"), {"display": "block"}, {"display": "none"}),
    ],
    progress=[
        Output("backfill-progress-bar", "value"),
        Output("backfill-progress-bar", "max"),
        Output("backfill-progress-label", "children"),
    ],
    prevent_initial_call=True,
)
def on_start_backfill(set_progress, n_clicks: int | None, account_id: int | None, start_date: str | None, end_date: str | None, chunk_size: int | None, current_version: int | None):
    if not n_clicks or not account_id or not start_date or not end_date:
        return current_version or 0, no_update, "", 0

    chunks = chunk_size or 14

    def cb(step: str, current: int, total: int) -> None:
        max_val = total if total else 1
        label = f"{step} ({current}/{max_val})"
        set_progress((current, max_val, label))

    res = health_service.run_chunked_backfill(
        account_id=account_id,
        start_date=start_date,
        end_date=end_date,
        chunk_days=chunks,
        progress_cb=cb,
    )

    new_version = (current_version or 0) + 1

    if res["status"] == "COMPLETE":
        alert = dbc.Alert(
            [
                html.Span("✅ ", className="me-1"),
                html.Strong("Backfill Complete! "),
                f"Historical data from {start_date} to {end_date} downloaded and materialized.",
            ],
            color="success",
            dismissable=True,
            className="mb-0",
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
            className="mb-0",
        )

    return new_version, alert, "", 0
