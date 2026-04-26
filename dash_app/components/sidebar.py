"""Left sidebar: app identity + data status + refresh control.

Owns the IDs that the sync background callback wires to (`refresh-btn`,
`sync-progress-bar`, `sync-progress-label`, `sync-status-pill`,
`data-extent-caption`) — moving them here is purely a layout change.
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import html


def render() -> html.Div:
    return html.Aside(
        [
            html.Div(
                [
                    html.Div(
                        "Data status", className="text-muted small text-uppercase mb-1"
                    ),
                    html.Div(id="sync-status-pill", className="mb-2"),
                    html.Small(id="data-extent-caption", className="text-muted d-block"),
                ],
                className="mb-3",
            ),
            dbc.Button(
                "Refresh",
                id="refresh-btn",
                color="primary",
                size="sm",
                className="w-100",
            ),
            dbc.Progress(
                id="sync-progress-bar",
                value=0,
                max=1,
                striped=True,
                animated=True,
                style={"display": "none"},
                className="mt-2",
            ),
            html.Small(
                id="sync-progress-label", className="text-muted d-block mt-1"
            ),
            html.Div(className="flex-grow-1"),
            html.Hr(className="my-3"),
            html.Small(
                "Powered by Octopus Energy Agile API",
                className="text-muted",
            ),
        ],
        className="setrum-sidebar d-flex flex-column",
    )
