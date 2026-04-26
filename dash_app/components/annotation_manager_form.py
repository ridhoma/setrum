"""Annotation Manager modal: explicit create / edit form.

Distinct from the chart-bound `annotation_form.py`:
  * The chart form prefills period from a brush selection and shows live
    aggregates as the brush moves.
  * This manager form lets the user pick period bounds with date pickers
    + hour / minute dropdowns. There's no live aggregate display since
    the user is constructing a period from scratch — kWh/£ surface only
    once the annotation is saved and rendered as a sticky note.
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dcc, html

HOUR_OPTIONS = [{"label": f"{h:02d}", "value": h} for h in range(24)]
MINUTE_OPTIONS = [{"label": "00", "value": 0}, {"label": "30", "value": 30}]


def _datetime_picker(prefix: str, label: str) -> dbc.Row:
    """`prefix` is 'from' or 'to'."""
    return dbc.Row(
        [
            dbc.Col(html.Small(label, className="text-muted"), md=2,
                    className="d-flex align-items-center"),
            dbc.Col(
                dcc.DatePickerSingle(
                    id=f"ann-mgr-{prefix}-date",
                    display_format="YYYY-MM-DD",
                    placeholder="Pick a date",
                    className="w-100",
                ),
                md=5,
            ),
            dbc.Col(
                html.Div(
                    [
                        dbc.Select(
                            id=f"ann-mgr-{prefix}-hour",
                            options=HOUR_OPTIONS,
                            value=0,
                            size="sm",
                            class_name="me-1",
                        ),
                        html.Span(":", className="me-1"),
                        dbc.Select(
                            id=f"ann-mgr-{prefix}-minute",
                            options=MINUTE_OPTIONS,
                            value=0,
                            size="sm",
                        ),
                    ],
                    id=f"ann-mgr-{prefix}-time-wrap",
                    className="d-flex align-items-center",
                ),
                md=5,
            ),
        ],
        className="mb-2 align-items-center",
    )


def render() -> dbc.Modal:
    return dbc.Modal(
        [
            dbc.ModalHeader(
                dbc.ModalTitle(id="ann-mgr-title"),
                close_button=True,
            ),
            dbc.ModalBody(
                [
                    dbc.Label("Assigned to chart"),
                    dbc.RadioItems(
                        id="ann-mgr-source",
                        options=[
                            {"label": "Daily",       "value": "daily"},
                            {"label": "Half-hourly", "value": "half-hourly"},
                        ],
                        value="half-hourly",
                        inline=True,
                        class_name="mb-3",
                    ),
                    dbc.Label("Period"),
                    _datetime_picker("from", "From"),
                    _datetime_picker("to",   "To"),
                    dbc.Label("Tags", className="mt-3"),
                    dcc.Dropdown(
                        id="ann-mgr-tags",
                        options=[],
                        multi=True,
                        placeholder="Add tags (type to create new)…",
                        className="mb-2",
                    ),
                    dbc.Label("Comment"),
                    dbc.Textarea(
                        id="ann-mgr-comment",
                        placeholder="Free-text note…",
                        rows=3,
                    ),
                    html.Div(id="ann-mgr-error", className="text-danger small mt-2"),
                ]
            ),
            dbc.ModalFooter(
                [
                    dbc.Button("Cancel", id="ann-mgr-cancel-btn",
                               color="secondary", outline=True),
                    dbc.Button("Save", id="ann-mgr-save-btn", color="primary"),
                ]
            ),
            # Internal state: { "mode": "create"|"edit", "annotation_id": int|None }
            dcc.Store(id="ann-mgr-mode-store", data={"mode": "create", "annotation_id": None}),
        ],
        id="ann-mgr-modal",
        is_open=False,
        size="lg",
    )
