"""Headline KPI cards. Sit inline with the daily-chart controls and respond
to that chart's date filter (driven by `summary` callback).
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import html


def _card(label: str, value_id: str) -> dbc.Card:
    return dbc.Card(
        dbc.CardBody(
            [
                html.Div(label, className="text-muted small text-uppercase summary-label"),
                html.H5(id=value_id, className="mb-0 fw-bold"),
            ],
            className="py-2 px-3",
        ),
        className="summary-card",
    )


def render() -> dbc.Row:
    """Inline row of 4 KPI cards. The caller decides outer width."""
    return dbc.Row(
        [
            dbc.Col(_card("Total Consumption",       "summary-kwh"),     md=3),
            dbc.Col(_card("Total Cost (incl. VAT)",  "summary-cost"),    md=3),
            dbc.Col(_card("Avg Price (incl. VAT)",   "summary-price"),   md=3),
            dbc.Col(_card("Avg Standing Charge",     "summary-standing"), md=3),
        ],
        className="g-2",
    )
