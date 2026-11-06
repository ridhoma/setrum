"""Data Health tab: telemetry availability tile heatmap, table audit, and chunked backfill."""

from __future__ import annotations

import datetime
import dash_bootstrap_components as dbc
from dash import dcc, html

from core.services import data_health as health_service


def render() -> html.Div:
    accounts = health_service.get_accounts()
    active_account = next((a for a in accounts if a["is_active"]), accounts[0] if accounts else None)
    active_id = active_account["account_id"] if active_account else None

    account_options = [
        {"label": a["display_name"], "value": a["account_id"]}
        for a in accounts
    ]

    today = datetime.date.today()
    default_start = today - datetime.timedelta(days=30)

    return html.Div(
        [
            # Editorial Section Header
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("IV. Telemetry Audit & Backfill", className="editorial-kicker"),
                            html.H1("Smart Meter Coverage & SQLite Health", className="editorial-h1"),
                        ]
                    ),
                    html.Div(
                        [
                            html.Span("Property:", className="me-2 small text-muted font-monospace text-uppercase"),
                            dcc.Dropdown(
                                id="health-account-select",
                                options=account_options,
                                value=active_id,
                                clearable=False,
                                className="setrum-dropdown",
                                style={"minWidth": "300px"},
                            ),
                        ],
                        className="d-flex align-items-center mt-2 mt-md-0",
                    ),
                ],
                className="editorial-section-head",
            ),

            # KPI Summary Row
            html.Div(id="health-kpi-container", className="mb-4"),

            # GitHub-Style Availability Calendar Heatmap Card
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.H5("Data Availability Heatmap", className="mb-1"),
                                    html.Small(
                                        "Daily interval coverage (green = 48/48 half-hour slots, yellow = partial, gray = missing)",
                                        className="text-muted",
                                    ),
                                ]
                            ),
                            html.Div(
                                [
                                    dbc.RadioItems(
                                        id="health-window-select",
                                        options=[
                                            {"label": "3 Months", "value": 90},
                                            {"label": "6 Months", "value": 180},
                                            {"label": "1 Year", "value": 365},
                                        ],
                                        value=365,
                                        inline=True,
                                        className="btn-group",
                                        inputClassName="btn-check",
                                        labelClassName="btn btn-outline-secondary btn-sm health-pill-btn",
                                        labelCheckedClassName="active",
                                    ),
                                ],
                                className="mt-2 mt-sm-0",
                            ),
                        ],
                        className="d-flex flex-column flex-sm-row justify-content-between align-items-sm-center mb-3",
                    ),

                    # Stream selector pills
                    html.Div(
                        [
                            html.Span("Target Stream:", className="small text-muted me-2 font-monospace text-uppercase"),
                            dbc.RadioItems(
                                id="health-table-select",
                                options=[
                                    {"label": "⚡ Half-Hourly Consumption", "value": "source_consumptions"},
                                    {"label": "💷 Standard Unit Rates", "value": "source_electricity_standard_unit_rates"},
                                    {"label": "🔌 Standing Charges", "value": "source_electricity_standing_charges"},
                                    {"label": "📊 Daily Analytics Mart", "value": "analytics_fct_consumptions_daily"},
                                ],
                                value="source_consumptions",
                                inline=True,
                                className="btn-group flex-wrap",
                                inputClassName="btn-check",
                                labelClassName="btn btn-outline-primary btn-sm health-pill-btn mb-1",
                                labelCheckedClassName="active",
                            ),
                        ],
                        className="d-flex align-items-center flex-wrap mb-3",
                    ),

                    # The Tile Grid host
                    html.Div(id="health-calendar-grid", className="mb-3"),

                    # Heatmap Legend
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Span("Legend:", className="me-2 text-muted"),
                                    html.Div(className="health-tile health-tile--missing me-1", title="Missing (0 slots)"),
                                    html.Span("Missing (0)", className="me-3"),
                                    html.Div(className="health-tile health-tile--partial me-1", title="Partial (1–47 slots)"),
                                    html.Span("Partial (1–47)", className="me-3"),
                                    html.Div(className="health-tile health-tile--complete me-1", title="Complete (48/48 slots)"),
                                    html.Span("Complete (48)"),
                                ],
                                className="health-legend",
                            ),
                            html.Small(
                                "Hover over any tile for date details. Click a date to inspect.",
                                className="text-muted ms-auto mt-1 mt-sm-0",
                            ),
                        ],
                        className="d-flex flex-column flex-sm-row align-items-sm-center justify-content-between pt-2 border-top",
                    ),
                ],
                className="health-calendar-container mb-4",
            ),

            # Row with Raw Tables Overview & Historical Backfill Orchestrator
            dbc.Row(
                [
                    # Raw Tables Overview
                    dbc.Col(
                        [
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.H5("Raw Ingestion Tables Audit", className="mb-1"),
                                            html.Small("State of local SQLite ingestion storage", className="text-muted"),
                                        ],
                                        className="p-3 border-bottom",
                                    ),
                                    html.Div(id="health-tables-overview-container", className="p-0"),
                                ],
                                className="health-table-card h-100",
                            ),
                        ],
                        width=12,
                        lg=6,
                        className="mb-4 mb-lg-0",
                    ),

                    # Historical Backfill Control Card
                    dbc.Col(
                        [
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.H5("Historical Backfill Orchestrator", className="mb-1"),
                                            html.Small(
                                                "Fetch historical smart meter & tariff data in chunked batches",
                                                className="text-muted",
                                            ),
                                        ],
                                        className="p-3 border-bottom",
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Date Range to Backfill", className="form-label small font-monospace text-uppercase text-muted"),
                                            html.Div(
                                                dcc.DatePickerRange(
                                                    id="backfill-date-picker",
                                                    start_date=default_start.isoformat(),
                                                    end_date=today.isoformat(),
                                                    max_date_allowed=today.isoformat(),
                                                    display_format="YYYY-MM-DD",
                                                    className="w-100 mb-2",
                                                ),
                                                className="mb-2",
                                            ),

                                            # Quick Presets
                                            html.Div(
                                                [
                                                    dbc.Button("Last 30 Days", id="backfill-preset-30d", size="sm", color="light", className="me-1 mb-1"),
                                                    dbc.Button("Last 90 Days", id="backfill-preset-90d", size="sm", color="light", className="me-1 mb-1"),
                                                    dbc.Button("2026 Year-to-Date", id="backfill-preset-ytd", size="sm", color="light", className="me-1 mb-1"),
                                                    dbc.Button("Since Move-in", id="backfill-preset-movein", size="sm", color="light", className="mb-1"),
                                                ],
                                                className="d-flex flex-wrap mb-3",
                                            ),

                                            html.Label("Chunk Size", className="form-label small font-monospace text-uppercase text-muted"),
                                            html.P(
                                                "Chunking downloads data in smaller time windows, avoiding API timeouts and materializing chunks incrementally.",
                                                className="small text-muted mb-2",
                                            ),
                                            dbc.RadioItems(
                                                id="backfill-chunk-size",
                                                options=[
                                                    {"label": "7 Days", "value": 7},
                                                    {"label": "14 Days (Recommended)", "value": 14},
                                                    {"label": "30 Days", "value": 30},
                                                ],
                                                value=14,
                                                inline=True,
                                                className="mb-3",
                                            ),

                                            dbc.Button(
                                                "🚀 Start Chunked Backfill",
                                                id="backfill-start-btn",
                                                className="btn-primary-editorial w-100 mb-3",
                                                size="md",
                                            ),

                                            # Progress bar and status feedback
                                            dbc.Progress(
                                                id="backfill-progress-bar",
                                                value=0,
                                                max=1,
                                                striped=True,
                                                animated=True,
                                                style={"display": "none"},
                                                className="mb-2",
                                            ),
                                            html.Div(
                                                id="backfill-progress-label",
                                                className="small text-muted mb-2 font-monospace",
                                            ),
                                            html.Div(id="backfill-status-alert"),
                                        ],
                                        className="p-3",
                                    ),
                                ],
                                className="health-table-card h-100",
                            ),
                        ],
                        width=12,
                        lg=6,
                    ),
                ]
            ),
        ],
        className="p-3 p-md-4",
    )
