"""Annotation callbacks: save, and render the sticky-note board.

Save handler snaps brushed ranges to half-hour boundaries so per-tag
SUMs line up cleanly with the half-hourly fact, and bumps
ANNOTATIONS_VERSION so all dependent views refresh.
"""

from __future__ import annotations

from dash import Input, Output, State, callback, no_update

from core.services import annotations as annotations_service
from dash_app import stores
from dash_app.components import annotations_board


@callback(
    Output(stores.ANNOTATIONS_VERSION, "data"),
    Output("ann-comment",              "value"),
    Output("ann-tags",                 "value"),
    Output("ann-save-feedback",        "children"),
    Input("ann-save-btn",              "n_clicks"),
    State("ann-comment",               "value"),
    State("ann-tags",                  "value"),
    State(stores.SELECTED_RANGE,       "data"),
    State(stores.ACTIVE_ACCOUNT_ID,    "data"),
    State(stores.ANNOTATIONS_VERSION,  "data"),
    prevent_initial_call=True,
)
def save_annotation(
    n_clicks: int | None,
    comment: str | None,
    tag_names: list | None,
    rng: dict | None,
    account_id: int | None,
    current_version: int | None,
):
    if not n_clicks or not rng or account_id is None:
        return no_update, no_update, no_update, no_update
    if not (comment or tag_names):
        return no_update, no_update, no_update, "Add a comment or at least one tag."

    period_start = annotations_service.snap_to_half_hour(rng["start"], direction="down")
    period_end = annotations_service.snap_to_half_hour(rng["end"], direction="up")
    if period_end <= period_start:
        return no_update, no_update, no_update, "Selected window is too short."

    annotations_service.create(
        account_id=account_id,
        period_start_utc=period_start,
        period_end_utc=period_end,
        source=rng.get("source", "half-hourly"),
        comment=(comment or "").strip() or None,
        tag_names=tag_names or [],
    )
    return (current_version or 0) + 1, "", [], "Saved."


@callback(
    Output("annotations-board", "children"),
    Input(stores.ANNOTATIONS_VERSION, "data"),
    Input(stores.DATA_VERSION,        "data"),
    Input(stores.ACTIVE_ACCOUNT_ID,   "data"),
)
def render_board(_av: int, _dv: int, account_id: int | None):
    df = annotations_service.list_all_with_aggregates(account_id=account_id)
    return annotations_board.render_notes(df)
