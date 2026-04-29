"""Annotations tab: header with '+ New' + pan/zoom canvas of sticky notes."""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dcc, html

from dash_app.components import annotations_board  # canvas + sticky-note rendering


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
    return html.Div(
        [
            html.Div(
                [
                    html.H3("Annotations", className="mb-0 me-3"),
                    html.Small(
                        "Drag to move notes. Scroll to pan, ⌘+scroll to zoom, "
                        "or hold space to pan with the mouse.",
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
                className="annotations-canvas-viewport",
            ),
        ]
    )
