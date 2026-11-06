"""Top header: Editorial Masthead with brand, nav tabs, and integrated sync status."""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dcc, html


def render() -> html.Header:
    brand = html.Div(
        [
            html.Div(
                [
                    html.Span("⚡", className="brand-bolt"),
                    html.Span("Setrum", className="brand-name"),
                ],
                className="brand-title",
            ),
            html.Span(
                ["Personal Energy Field Journal", html.Br(), "• Local SQLite"],
                className="brand-subtitle",
            ),
        ],
        className="brand-group",
    )

    nav = dcc.Tabs(
        id="main-tabs",
        value="consumptions",
        className="nav-tabs",
        parent_className="nav-tabs-wrap",
        children=[
            dcc.Tab(
                label="📈 Consumptions",
                value="consumptions",
                className="nav-tab",
                selected_className="nav-tab active",
            ),
            dcc.Tab(
                label=html.Span(["📌 Corkboard ", html.Span("0", id="nav-ann-count", className="tab-count")]),
                value="annotations",
                className="nav-tab",
                selected_className="nav-tab active",
            ),
            dcc.Tab(
                label="✨ Tag Insights",
                value="insights",
                className="nav-tab",
                selected_className="nav-tab active",
            ),
            dcc.Tab(
                label="🩺 Data Health",
                value="data_health",
                className="nav-tab",
                selected_className="nav-tab active",
            ),
        ],
    )

    status_cluster = html.Div(
        [
            html.Div(id="sync-status-pill", className="sync-pill-container"),
            html.Small(id="data-extent-caption", style={"display": "none"}),
            dbc.Button(
                "↻ Sync Octopus",
                id="refresh-btn",
                className="btn-secondary-editorial",
                size="sm",
            ),
            dbc.Button(
                "📓 Field Notes Rail",
                id="toggle-rail-btn",
                className="btn-secondary-editorial active",
                size="sm",
                title="Toggle side field-notes drawer",
            ),
            dbc.Progress(
                id="sync-progress-bar",
                value=0,
                max=1,
                striped=True,
                animated=True,
                style={"display": "none"},
                className="masthead-progress-bar",
            ),
            html.Small(
                id="sync-progress-label",
                className="masthead-progress-label",
            ),
        ],
        className="masthead-status",
    )

    return html.Header(
        [brand, nav, status_cluster],
        className="setrum-header masthead",
    )
