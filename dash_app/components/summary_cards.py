"""Headline KPI cards — Option 1: Editorial KPI Strip.

Responds to the daily chart's date filter (driven by `summary` callback).
"""

from __future__ import annotations

from dash import html


def render() -> html.Div:
    """Editorial 4-column KPI strip."""
    return html.Div(
        [
            html.Div(
                [
                    html.Div("Total Consumption", className="kpi-label"),
                    html.Div("—", id="summary-kwh", className="kpi-value"),
                    html.Div(
                        [
                            html.Span("↓ 6.4%", className="delta-badge delta-down me-1"),
                            "vs prior period",
                        ],
                        className="kpi-sub",
                    ),
                ],
                className="kpi-cell hero",
            ),
            html.Div(
                [
                    html.Div("Total Period Cost", className="kpi-label"),
                    html.Div("—", id="summary-cost", className="kpi-value"),
                    html.Div("Usage + SC + VAT", className="kpi-sub"),
                ],
                className="kpi-cell",
            ),
            html.Div(
                [
                    html.Div("Effective Unit Rate", className="kpi-label"),
                    html.Div("—", id="summary-price", className="kpi-value"),
                    html.Div("Flexible Octopus • Excl. VAT", className="kpi-sub"),
                ],
                className="kpi-cell",
            ),
            html.Div(
                [
                    html.Div("Standing Charge", className="kpi-label"),
                    html.Div("—", id="summary-standing", className="kpi-value"),
                    html.Div("Daily fixed metering charge", className="kpi-sub"),
                ],
                className="kpi-cell",
            ),
        ],
        className="kpi-strip",
    )
