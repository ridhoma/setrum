"""Consumptions tab: daily cost/consumption chart + half-hourly chart."""

from __future__ import annotations

from dash import html

from dash_app.components import daily_cost_chart, hh_chart


def render() -> html.Div:
    return html.Div(
        [
            daily_cost_chart.render(),
            html.Div(hh_chart.render(), className="mt-4"),
        ]
    )
