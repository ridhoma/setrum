"""Consumptions tab — Option 1: Editorial Field Notes.

Section header with controls + 4-column KPI strip + daily bar chart + half-hourly depth profile.
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import html

from dash_app.components import (
    daily_cost_chart,
    date_range_filter,
    hh_chart,
    hourly_profile_table,
    summary_cards,
)


def render() -> html.Div:
    view_toggle = html.Div(
        dbc.RadioItems(
            id="daily-view-toggle",
            options=[
                {"label": "£ Sterling", "value": "cost"},
                {"label": "kWh Energy", "value": "kwh"},
            ],
            value="cost",
            class_name="segmented-group",
            input_class_name="btn-check",
            label_class_name="seg-btn",
            label_checked_class_name="active",
        ),
        className="setrum-toggle",
    )

    section_head = html.Div(
        [
            html.Div(
                [
                    html.Div("I. Meter Telemetry & Cost Breakdown", className="editorial-kicker"),
                    html.H1("Household Electricity Ledger", className="editorial-h1"),
                ]
            ),
            html.Div(
                [
                    view_toggle,
                    date_range_filter.render(
                        "daily",
                        presets=[
                            ("7D", 7),
                            ("14D", 14),
                            ("30D", 30),
                            ("90D", 90),
                        ],
                        default_days=30,
                    ),
                ],
                className="control-cluster",
            ),
        ],
        className="editorial-section-head",
    )

    bottom_row = html.Div(
        [
            html.Div(hourly_profile_table.render(), className="consumption-col-left"),
            html.Div(hh_chart.render(), className="consumption-col-right"),
        ],
        className="consumption-bottom-grid",
    )

    return html.Div(
        [
            section_head,
            summary_cards.render(),
            daily_cost_chart.render(),
            bottom_row,
        ]
    )
