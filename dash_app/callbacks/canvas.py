"""Persist sticky-note canvas positions on drop.

The browser's drag JS writes a `{id, x, y, ts}` payload to
`sticky-position-store` whenever the user releases a sticky note.
This callback turns that payload into a single SQLite UPDATE via
`services.annotations.set_position`. We deliberately do *not* bump
`ANNOTATIONS_VERSION` — the DOM is already at the correct position from
the JS drag, so a re-render would be wasted and would cause a brief
visual jitter.
"""

from __future__ import annotations

from dash import Input, Output, callback, no_update

from core.services import annotations as annotations_service


@callback(
    Output("sticky-position-status", "children"),
    Input("sticky-position-store", "data"),
    prevent_initial_call=True,
)
def persist_sticky_position(payload: dict | None):
    if not payload:
        return no_update
    try:
        ann_id = int(payload["id"])
        x = int(payload["x"])
        y = int(payload["y"])
    except (KeyError, TypeError, ValueError):
        return no_update
    annotations_service.set_position(ann_id, x, y)
    return ""  # dummy update — value is irrelevant
