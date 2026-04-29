"""Persist sticky-note canvas positions on drop.

The browser's drag JS writes either a single `{id, x, y, ts}` payload
(legacy single-drag) or a batch `{updates: [{id, x, y}, ...], ts}` payload
(multi-drag) to `sticky-position-store` whenever the user releases a
sticky note. This callback turns that payload into one or more SQLite
UPDATEs via `services.annotations.set_position[s]`. We deliberately do
*not* bump `ANNOTATIONS_VERSION` — the DOM is already at the correct
position from the JS drag, so a re-render would be wasted and would
cause a brief visual jitter.
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

    # Multi-drag: batch of updates, persisted atomically.
    if isinstance(payload, dict) and "updates" in payload:
        records = []
        for u in payload.get("updates") or []:
            try:
                records.append({
                    "id": int(u["id"]),
                    "x": int(u["x"]),
                    "y": int(u["y"]),
                })
            except (KeyError, TypeError, ValueError):
                continue
        if records:
            annotations_service.set_positions(records)
        return ""

    # Single-drag: legacy {id, x, y, ts} payload.
    try:
        ann_id = int(payload["id"])
        x = int(payload["x"])
        y = int(payload["y"])
    except (KeyError, TypeError, ValueError):
        return no_update
    annotations_service.set_position(ann_id, x, y)
    return ""  # dummy update — value is irrelevant
