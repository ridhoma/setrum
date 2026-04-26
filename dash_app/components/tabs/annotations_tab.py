"""Annotations tab: header with '+ New' + draggable canvas of sticky notes."""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dcc, html

from dash_app.components import annotations_board  # canvas + sticky-note rendering


def render() -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.H3("Annotations", className="mb-0 me-3"),
                    html.Small(
                        "Drag notes around to organise them — positions are saved.",
                        className="text-muted me-auto",
                    ),
                    dbc.Button(
                        ["+ New"],
                        id="ann-mgr-new-btn",
                        color="primary",
                        size="sm",
                    ),
                ],
                className="d-flex align-items-center mb-3",
            ),
            html.Div(
                [
                    html.Div(
                        id="annotations-board",
                        className="annotations-canvas",
                    ),
                    # Side-effect callback writes drag-end positions here so the
                    # server can persist via annotations_service.set_position.
                    dcc.Store(id="sticky-position-store"),
                    html.Div(id="sticky-position-status", style={"display": "none"}),
                ],
                id="annotations-canvas-viewport",
                className="annotations-canvas-viewport",
            ),
        ]
    )
