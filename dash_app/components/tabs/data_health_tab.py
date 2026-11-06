"""Data Health tab — Option A: Editorial Ledger & Responsive Coverage Matrix.

Features:
- 5-cell Editorial KPI Strip
- Full-width CSS-Grid 52-week Coverage Matrix with interactive single-tile and
  range-of-tiles selection + direct 1-click backfill from the matrix inspector bar
- 2-column bottom split: SQLite Storage & Pipeline Ledger + Historical Backfill Workbench
"""

from __future__ import annotations

import datetime
import dash_bootstrap_components as dbc
from dash import dcc, html

from core.services import data_health as health_service


def render() -> html.Div:
    accounts = health_service.get_accounts()
    active_account = next(
        (a for a in accounts if a["is_active"]),
        accounts[0] if accounts else None,
    )
    active_id = active_account["account_id"] if active_account else None

    account_options = [
        {"label": a["display_name"], "value": a["account_id"]}
        for a in accounts
    ]

    today = datetime.date.today()
    default_start = today - datetime.timedelta(days=30)

    return html.Div(
        [
            # Store for tile / tile-range selection on the coverage matrix
            dcc.Store(id="health-tile-selection", data=None),

            # Editorial Section Header
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                "IV. Telemetry Audit & Historical Backfill",
                                className="editorial-kicker",
                            ),
                            html.H1(
                                "Smart Meter Coverage & SQLite Health",
                                className="editorial-h1",
                            ),
                        ]
                    ),
                    html.Div(
                        [
                            html.Span("PROPERTY:", className="dh-prop-label"),
                            dcc.Dropdown(
                                id="health-account-select",
                                options=account_options,
                                value=active_id,
                                clearable=False,
                                className="dh-prop-dropdown",
                            ),
                        ],
                        className="dh-property-pill",
                    ),
                ],
                className="editorial-section-head",
            ),

            # 5-Column Editorial KPI Strip
            html.Div(id="health-kpi-container"),

            # Full-Width Daily Settlement Coverage Matrix Card
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.H3(
                                        "Daily Settlement Coverage Matrix",
                                        className="mb-0",
                                    ),
                                    html.P(
                                        "Click any day tile to inspect its 48 half-hour slots, or click a start tile then an end tile to select a date range and backfill directly",
                                        className="text-muted small mb-0",
                                    ),
                                ],
                                className="chart-title-wrap flex-grow-1",
                            ),
                            html.Div(
                                [
                                    dbc.RadioItems(
                                        id="health-table-select",
                                        options=[
                                            {"label": "⚡ Consumption", "value": "source_consumptions"},
                                            {"label": "💷 Unit Rates", "value": "source_electricity_standard_unit_rates"},
                                            {"label": "🔌 Standing Charge", "value": "source_electricity_standing_charges"},
                                            {"label": "📊 Daily Mart", "value": "analytics_fct_consumptions_daily"},
                                        ],
                                        value="source_consumptions",
                                        class_name="segmented-group",
                                        input_class_name="btn-check",
                                        label_class_name="seg-btn",
                                        label_checked_class_name="active",
                                    ),
                                    dbc.RadioItems(
                                        id="health-window-select",
                                        options=[
                                            {"label": "3M", "value": 90},
                                            {"label": "6M", "value": 180},
                                            {"label": "1Y", "value": 365},
                                        ],
                                        value=365,
                                        class_name="segmented-group",
                                        input_class_name="btn-check",
                                        label_class_name="seg-btn",
                                        label_checked_class_name="active",
                                    ),
                                ],
                                className="dh-controls-row",
                            ),
                        ],
                        className="chart-card-header daily-chart-card-header",
                    ),

                    # Heatmap Box (Grid + Interactive Selection & Backfill Inspector Bar)
                    html.Div(
                        [
                            html.Div(id="health-calendar-grid"),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Span(
                                                [
                                                    html.I(className="dh-legend-dot dh-dot-missing"),
                                                    "Pre-Move-In / Missing (0/48)",
                                                ],
                                                className="dh-legend-item",
                                            ),
                                            html.Span(
                                                [
                                                    html.I(className="dh-legend-dot dh-dot-partial"),
                                                    "Partial (1–47 slots)",
                                                ],
                                                className="dh-legend-item",
                                            ),
                                            html.Span(
                                                [
                                                    html.I(className="dh-legend-dot dh-dot-complete"),
                                                    "Complete (48/48 slots)",
                                                ],
                                                className="dh-legend-item",
                                            ),
                                        ],
                                        className="dh-legend-group",
                                    ),
                                    html.Div(
                                        [
                                            html.Span(
                                                id="health-selection-summary",
                                                className="dh-inspector-summary",
                                            ),
                                            html.Div(
                                                id="health-selection-strip",
                                                className="dh-mini-slot-strip",
                                            ),
                                            dbc.Button(
                                                "↻ Backfill Selection",
                                                id="matrix-backfill-btn",
                                                color="link",
                                                size="sm",
                                                className="dh-matrix-backfill-btn",
                                                title="Immediately fetch & rebuild analytics for the selected tile(s)",
                                            ),
                                            dbc.Button(
                                                "✕",
                                                id="matrix-clear-btn",
                                                color="link",
                                                size="sm",
                                                className="dh-matrix-clear-btn",
                                                title="Clear tile selection",
                                            ),
                                        ],
                                        id="health-inspector-pill",
                                        className="dh-inspector-pill",
                                    ),
                                ],
                                className="dh-day-inspector-bar",
                            ),
                        ],
                        className="dh-heatmap-box",
                    ),
                ],
                className="chart-card",
            ),

            # Bottom 2-Column Split: SQLite Storage Ledger + Historical Backfill Workbench
            html.Div(
                [
                    # Left: SQLite Storage & Pipeline Ledger
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.H3("SQLite Storage & Pipeline Ledger", className="mb-0"),
                                            html.P(
                                                "Row counts, date boundaries, and health across raw ingestion and ELT mart tables",
                                                className="text-muted small mb-0",
                                            ),
                                        ],
                                        className="chart-title-wrap",
                                    ),
                                ],
                                className="chart-card-header",
                            ),
                            html.Div(id="health-tables-overview-container"),
                        ],
                        className="chart-card mb-0 h-100",
                    ),

                    # Right: Historical Backfill Workbench
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.H3("Historical Backfill Workbench", className="mb-0"),
                                            html.P(
                                                "Download or repair historical smart-meter & tariff windows in safe API batches",
                                                className="text-muted small mb-0",
                                            ),
                                        ],
                                        className="chart-title-wrap",
                                    ),
                                ],
                                className="chart-card-header",
                            ),
                            html.Div(
                                [
                                    html.Label(
                                        "Target Date Window (Synced with Tile Matrix Selection)",
                                        className="dh-form-label",
                                    ),
                                    html.Div(
                                        dcc.DatePickerRange(
                                            id="backfill-date-picker",
                                            start_date=default_start.isoformat(),
                                            end_date=today.isoformat(),
                                            max_date_allowed=today.isoformat(),
                                            display_format="YYYY-MM-DD",
                                            className="dh-date-picker-range w-100",
                                        ),
                                        className="mb-2",
                                    ),
                                    html.Div(
                                        [
                                            dbc.Button("Prev 30D", id="backfill-preset-30d", size="sm", color="light", className="dh-preset-chip"),
                                            dbc.Button("Prev 90D", id="backfill-preset-90d", size="sm", color="light", className="dh-preset-chip"),
                                            dbc.Button("2026 YTD", id="backfill-preset-ytd", size="sm", color="light", className="dh-preset-chip"),
                                            dbc.Button("Since Move-In", id="backfill-preset-movein", size="sm", color="light", className="dh-preset-chip"),
                                        ],
                                        className="dh-preset-row mb-3",
                                    ),
                                    html.Label(
                                        "Batch Chunk Window (API Rate-Limit Guard)",
                                        className="dh-form-label",
                                    ),
                                    dbc.RadioItems(
                                        id="backfill-chunk-size",
                                        options=[
                                            {"label": "7 Days", "value": 7},
                                            {"label": "14 Days (Rec.)", "value": 14},
                                            {"label": "30 Days", "value": 30},
                                        ],
                                        value=14,
                                        class_name="segmented-group dh-chunk-segmented mb-3",
                                        input_class_name="btn-check",
                                        label_class_name="seg-btn",
                                        label_checked_class_name="active",
                                    ),
                                    dbc.Button(
                                        "↻ Run Chunked Backfill & Rebuild Marts",
                                        id="backfill-start-btn",
                                        className="btn-primary-editorial w-100 py-2",
                                    ),
                                    dbc.Progress(
                                        id="backfill-progress-bar",
                                        value=0,
                                        max=1,
                                        striped=True,
                                        animated=True,
                                        style={"display": "none"},
                                        className="mt-3 mb-1",
                                    ),
                                    html.Div(
                                        id="backfill-progress-label",
                                        className="small text-muted font-monospace mt-1",
                                    ),
                                    html.Div(id="backfill-status-alert", className="mt-2"),
                                ]
                            ),
                        ],
                        className="chart-card mb-0 h-100",
                    ),
                ],
                className="dh-bottom-grid",
            ),
        ],
    )
