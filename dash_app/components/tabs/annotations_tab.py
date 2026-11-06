"""Annotations tab — Option 1: Editorial Field Notes.

Header with '+ New Field Note' + pan/zoom canvas of sticky notes on warm dotted corkboard.
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dcc, html

from dash_app.components import annotations_board


def _zoom_controls() -> html.Div:
    """Bottom-right zoom pill — purely client-side, driven by canvas_pan_zoom.js."""
    return html.Div(
        [
            html.Button("−", className="zoom-btn", **{"data-action": "zoom-out"}, title="Zoom out"),
            html.Button("100%", className="zoom-btn zoom-readout",
                       **{"data-action": "reset"}, title="Reset zoom"),
            html.Button("+", className="zoom-btn", **{"data-action": "zoom-in"}, title="Zoom in"),
            html.Span(className="zoom-divider"),
            html.Button("Fit", className="zoom-btn zoom-btn-text",
                       **{"data-action": "fit"}, title="Fit notes to view"),
        ],
        className="canvas-zoom-controls",
    )


def render() -> html.Div:
    section_head = html.Div(
        [
            html.Div(
                [
                    html.Div("II. Spatial Observation Board", className="editorial-kicker"),
                    html.H1("The Energy Lab Corkboard", className="editorial-h1"),
                ]
            ),
            dbc.Button(
                "+ New Field Note",
                id="ann-mgr-new-btn",
                className="btn-primary-editorial",
                title="New field note",
            ),
        ],
        className="editorial-section-head",
    )
    return html.Div(
        [
            section_head,
            html.P(
                "Drag sticky notes anywhere on the board to cluster your household experiments. Positions persist in SQLite.",
                style={"marginBottom": "14px", "color": "var(--setrum-ink-700)"},
            ),
            html.Div(
                [
                    # Transformed content layer — pan/zoom JS applies CSS transform here.
                    html.Div(
                        html.Div(
                            id="annotations-board",
                            className="annotations-canvas",
                        ),
                        id="annotations-canvas-content",
                        className="annotations-canvas-content",
                    ),
                    _zoom_controls(),
                    # Side-effect callback writes drag-end positions here so the
                    # server can persist via annotations_service.set_position.
                    dcc.Store(id="sticky-position-store"),
                    html.Div(id="sticky-position-status", style={"display": "none"}),
                ],
                id="annotations-canvas-viewport",
                className="annotations-canvas-viewport corkboard-viewport",
            ),
        ]
    )
