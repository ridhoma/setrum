"""Consumptions tab — Option 1: Editorial Field Notes.

Section header with controls + 4-column KPI strip + daily bar chart + half-hourly depth profile.
"""

from __future__ import annotations

from dash import html

from dash_app.components import (
    daily_cost_chart,
    hh_chart,
    hourly_profile_table,
    summary_cards,
)


def render() -> html.Div:
    section_head = html.Div(
        [
            html.Div(
                [
                    html.Div("I. Meter Telemetry & Cost Breakdown", className="editorial-kicker"),
                    html.H1("Household Electricity Ledger", className="editorial-h1"),
                ]
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
