"""Top header: brand + 3-tab navigation."""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dcc, html


def render() -> html.Header:
    return html.Header(
        [
            html.Div(
                [
                    html.Span("⚡", className="setrum-brand-bolt"),
                    html.Span("Setrum Analyser", className="setrum-brand-name"),
                ],
                className="setrum-brand",
            ),
            dcc.Tabs(
                id="main-tabs",
                value="consumptions",
                className="setrum-tabs",
                parent_className="setrum-tabs-wrap",
                children=[
                    dcc.Tab(
                        label="📈  Consumptions",
                        value="consumptions",
                        className="setrum-tab",
                        selected_className="setrum-tab--active",
                    ),
                    dcc.Tab(
                        label="📝  Annotations",
                        value="annotations",
                        className="setrum-tab",
                        selected_className="setrum-tab--active",
                    ),
                    dcc.Tab(
                        label="✨  Insights",
                        value="insights",
                        className="setrum-tab",
                        selected_className="setrum-tab--active",
                    ),
                ],
            ),
        ],
        className="setrum-header",
    )
