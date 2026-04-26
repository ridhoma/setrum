"""Annotation form panel — rendered as a floating card over the HH chart.

Visibility is controlled by callbacks in `selection.py` based on the edit
button (`hh-readout-edit`), the close button (`ann-close-btn`), and the
save button (via `ANNOTATIONS_VERSION` bumps).
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dcc, html


def render() -> dbc.Card:
    return dbc.Card(
        [
            dbc.CardHeader(
                html.Div(
                    [
                        html.Span("📝 Annotate selection"),
                        dbc.Button(
                            "✕",
                            id="ann-close-btn",
                            color="link",
                            size="sm",
                            className="ann-close-btn p-0",
                            title="Cancel",
                        ),
                    ],
                    className="d-flex justify-content-between align-items-center",
                )
            ),
            dbc.CardBody(
                [
                    html.Div(
                        [
                            html.Small("Period", className="text-muted"),
                            html.Div(id="ann-period-display", className="mb-2"),
                            html.Small("Live aggregates", className="text-muted"),
                            html.Div(
                                [
                                    html.Span(id="ann-kwh-display", className="me-3"),
                                    html.Span(id="ann-cost-display"),
                                ],
                                className="mb-3",
                            ),
                        ]
                    ),
                    dbc.Label("Tags"),
                    dcc.Dropdown(
                        id="ann-tags",
                        options=[],
                        multi=True,
                        placeholder="Add tags (type to create new)…",
                        className="mb-2",
                    ),
                    dbc.Label("Comment"),
                    dbc.Textarea(
                        id="ann-comment",
                        placeholder="Free-text note…",
                        rows=3,
                        className="mb-2",
                    ),
                    dbc.Button(
                        "Save",
                        id="ann-save-btn",
                        color="primary",
                        size="sm",
                        disabled=True,
                    ),
                    html.Div(id="ann-save-feedback", className="text-success small mt-2"),
                ]
            ),
        ],
        id="ann-form-card",
        className="ann-form-card shadow-lg",
        style={"display": "none"},
    )
