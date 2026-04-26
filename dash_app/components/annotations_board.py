"""Annotations canvas — every annotation rendered as an absolutely-positioned
sticky note. Positions persist in `annotations.position_x / position_y`;
NULL coords trigger a default grid layout so newly-created notes stack
neatly to the top-left until the user drags them.

Drag handling lives in `dash_app/assets/canvas_drag.js` — pointer events
write the new (x, y) into `sticky-position-store`, and a Python callback
persists via `services.annotations.set_position`.
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
import pandas as pd
from dash import html

from dash_app.components.annotation_format import (
    format_period as _format_period,
    safe_str as _safe_str,
    split_pipe as _split_pipe,
)

# Default grid layout for notes that don't yet have a manual position.
GRID_COLS    = 4
NOTE_WIDTH   = 240
NOTE_HEIGHT  = 200
GRID_X_GAP   = 24
GRID_Y_GAP   = 28
GRID_PAD_X   = 24
GRID_PAD_Y   = 24


def _default_position(idx: int) -> tuple[int, int]:
    col = idx % GRID_COLS
    row = idx // GRID_COLS
    x = GRID_PAD_X + col * (NOTE_WIDTH + GRID_X_GAP)
    y = GRID_PAD_Y + row * (NOTE_HEIGHT + GRID_Y_GAP)
    return x, y


def _source_badge(source: str | None) -> html.Span:
    label = "DAILY" if source == "daily" else "HH"
    cls = "sticky-source-daily" if source == "daily" else "sticky-source-hh"
    return html.Span(label, className=f"sticky-source-badge {cls}")


def _coerce_position(value) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _sticky_note(row: pd.Series, idx: int) -> html.Div:
    ann_id = int(row["id"])
    tags = _split_pipe(row.get("tag_names"))
    period_label = _format_period(row["period_start_utc"], row["period_end_utc"])
    comment = _safe_str(row.get("comment")).strip() or "(no comment)"
    cost_pounds = float(row.get("cost_pence_inc_vat") or 0) / 100
    kwh = float(row.get("kwh") or 0)
    source = _safe_str(row.get("source")) or "half-hourly"

    px = _coerce_position(row.get("position_x"))
    py = _coerce_position(row.get("position_y"))
    if px is None or py is None:
        gx, gy = _default_position(idx)
        px = gx if px is None else px
        py = gy if py is None else py

    return html.Div(
        [
            # Top row: source badge on the left, edit + delete icons on the right.
            html.Div(
                [
                    _source_badge(source),
                    html.Div(
                        [
                            dbc.Button(
                                "✏️",
                                id={"type": "ann-edit-btn", "id": ann_id},
                                color="link",
                                size="sm",
                                className="sticky-action-btn p-0 me-1",
                                title="Edit",
                            ),
                            dbc.Button(
                                "🗑",
                                id={"type": "ann-delete-btn", "id": ann_id},
                                color="link",
                                size="sm",
                                className="sticky-action-btn p-0",
                                title="Delete",
                            ),
                        ],
                        className="sticky-actions",
                    ),
                ],
                className="sticky-toolbar",
            ),
            html.Div(period_label, className="sticky-period"),
            html.Div(comment, className="sticky-comment"),
            html.Div(
                [
                    html.Span(f"{kwh:.2f} kWh", className="me-2"),
                    html.Span(f"£{cost_pounds:.2f}"),
                ],
                className="sticky-stats",
            ),
            html.Div(
                [html.Span(t, className="sticky-tag") for t in tags],
                className="sticky-tags",
            ) if tags else None,
        ],
        # Stable element id keyed by annotation id so the drag JS can read
        # it via `el.id.replace("canvas-sticky-", "")`.
        id=f"canvas-sticky-{ann_id}",
        className="sticky-note canvas-sticky",
        style={"left": f"{px}px", "top": f"{py}px"},
    )


def render_notes(df: pd.DataFrame):
    if df is None or df.empty:
        return html.Div(
            "No annotations yet. Brush a chart and click ✏️ to pin one here, "
            "or use + New above.",
            className="text-muted text-center py-5 canvas-empty",
        )
    return [_sticky_note(row, idx) for idx, (_, row) in enumerate(df.iterrows())]
