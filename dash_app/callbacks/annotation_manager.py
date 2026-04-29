"""Annotation manager: open / close / save / delete + tag autocomplete.

The modal opens in three ways:
  * `+ New` button → create mode
  * Sticky note ✏️ icon (pattern matched) → edit mode, values prefilled
  * Click the 📝 icon on a chart annotation band → edit mode

🗑 (sticky) deletes via a separate pattern-matched callback. Closing
always bumps `ANNOTATIONS_VERSION` so the board, chart overlays, and
form options refresh together.
"""

from __future__ import annotations

import pandas as pd
from dash import ALL, Input, Output, State, callback, ctx, no_update

from core.services import annotations as annotations_service
from core.services import tags as tags_service
from dash_app import stores

_NUM_FORM_OUTPUTS = 13  # is_open, mode, title, source, 6 datetime fields, tags, comment, error


def _empty_form_outputs(is_open=False, mode=None, error=""):
    """Helper: produce a tuple matching every output of `manage_modal`."""
    return (
        is_open,
        mode if mode is not None else {"mode": "create", "annotation_id": None},
        no_update,                                # title
        no_update,                                # source
        no_update, no_update, no_update,          # from-date, hour, minute
        no_update, no_update, no_update,          # to-date,   hour, minute
        no_update,                                # tags
        no_update,                                # comment
        error,                                    # error msg
        no_update,                                # version
    )


def _open_for_edit(ann_id: int):
    """Build the form-output tuple for opening the modal in edit mode for
    `ann_id`. Used by both the sticky ✏️ button and chart 📝 icon clicks.
    """
    ann = annotations_service.get_by_id(ann_id)
    if not ann:
        return _empty_form_outputs(error=f"Annotation #{ann_id} not found.")

    ps = pd.to_datetime(ann["period_start_utc"])
    pe = pd.to_datetime(ann["period_end_utc"])
    src = ann.get("source") or "half-hourly"

    if src == "daily":
        from_d = ps.date().isoformat()
        # period_end is exclusive next midnight; show last *included* day.
        to_d = (pe - pd.Timedelta(days=1)).date().isoformat()
        from_h, from_m, to_h, to_m = 0, 0, 0, 0
    else:
        from_d = ps.date().isoformat()
        to_d   = pe.date().isoformat()
        from_h, from_m = int(ps.hour), int(ps.minute)
        to_h,   to_m   = int(pe.hour), int(pe.minute)

    return (
        True,
        {"mode": "edit", "annotation_id": ann_id},
        f"Edit annotation #{ann_id}",
        src,
        from_d, from_h, from_m,
        to_d,   to_h,   to_m,
        [t["name"] for t in ann.get("tags", [])],
        ann.get("comment") or "",
        "",
        no_update,
    )


def _annotation_id_from_click(click_data: dict | None) -> int | None:
    """Pull the annotation id off a chart click, or None if the click was
    on a bar / area / blank space (i.e. anything other than the 📝 icon)."""
    if not click_data:
        return None
    points = click_data.get("points") or []
    for p in points:
        cd = p.get("customdata")
        # Annotation icon traces use a single-int customdata; bar traces use
        # a 2-element list (cost_exc, cost_inc). Differentiate by type.
        if isinstance(cd, int):
            return cd
        if isinstance(cd, list) and len(cd) == 1 and isinstance(cd[0], int):
            return int(cd[0])
    return None


def _build_period(source, from_date, from_hour, from_minute, to_date, to_hour, to_minute):
    if not from_date or not to_date:
        raise ValueError("Pick both 'from' and 'to' dates.")

    if source == "daily":
        period_start = f"{from_date}T00:00:00+00:00"
        # 'to' date is inclusive in daily mode; period end is the next midnight.
        end_day = pd.to_datetime(to_date).date() + pd.Timedelta(days=1)
        period_end = f"{end_day.isoformat()}T00:00:00+00:00"
    else:
        fh = int(from_hour) if from_hour is not None else 0
        fm = int(from_minute) if from_minute is not None else 0
        th = int(to_hour)   if to_hour   is not None else 0
        tm = int(to_minute) if to_minute is not None else 0
        period_start = f"{from_date}T{fh:02d}:{fm:02d}:00+00:00"
        period_end   = f"{to_date}T{th:02d}:{tm:02d}:00+00:00"

    if period_end <= period_start:
        raise ValueError("'To' must be after 'From'.")
    return period_start, period_end


@callback(
    Output("ann-mgr-modal",          "is_open"),
    Output("ann-mgr-mode-store",     "data"),
    Output("ann-mgr-title",          "children"),
    Output("ann-mgr-source",         "value"),
    Output("ann-mgr-from-date",      "date"),
    Output("ann-mgr-from-hour",      "value"),
    Output("ann-mgr-from-minute",    "value"),
    Output("ann-mgr-to-date",        "date"),
    Output("ann-mgr-to-hour",        "value"),
    Output("ann-mgr-to-minute",      "value"),
    Output("ann-mgr-tags",           "value"),
    Output("ann-mgr-comment",        "value"),
    Output("ann-mgr-error",          "children"),
    Output(stores.ANNOTATIONS_VERSION, "data", allow_duplicate=True),
    Input("ann-mgr-new-btn",                          "n_clicks"),
    Input({"type": "ann-edit-btn", "id": ALL},        "n_clicks"),
    Input("ann-mgr-cancel-btn",                       "n_clicks"),
    Input("ann-mgr-save-btn",                         "n_clicks"),
    # Charts only exist on the Consumptions tab; the manager modal lives at
    # layout level, so these inputs must be optional or Dash refuses to fire
    # the callback for ANY input (incl. the sticky-note ✏️ pattern-match)
    # whenever the active tab doesn't mount these components.
    Input("hh-chart",                                 "clickData", allow_optional=True),
    Input("daily-cost-chart",                         "clickData", allow_optional=True),
    State("ann-mgr-mode-store",                       "data"),
    State("ann-mgr-source",                           "value"),
    State("ann-mgr-from-date",                        "date"),
    State("ann-mgr-from-hour",                        "value"),
    State("ann-mgr-from-minute",                      "value"),
    State("ann-mgr-to-date",                          "date"),
    State("ann-mgr-to-hour",                          "value"),
    State("ann-mgr-to-minute",                        "value"),
    State("ann-mgr-tags",                             "value"),
    State("ann-mgr-comment",                          "value"),
    State(stores.ACTIVE_ACCOUNT_ID,                   "data"),
    State(stores.ANNOTATIONS_VERSION,                 "data"),
    prevent_initial_call=True,
)
def manage_modal(
    _new_n,
    _edit_clicks,
    _cancel_n,
    _save_n,
    hh_click,
    daily_click,
    mode_data,
    source,
    from_date, from_hour, from_minute,
    to_date,   to_hour,   to_minute,
    tags, comment,
    account_id,
    current_version,
):
    triggered = ctx.triggered_id

    # ── + New ────────────────────────────────────────────────────────────
    if triggered == "ann-mgr-new-btn":
        return (
            True,                                                        # is_open
            {"mode": "create", "annotation_id": None},
            "New annotation",
            "half-hourly",
            None, 0, 0,
            None, 0, 0,
            [],
            "",
            "",
            no_update,
        )

    # ── Edit via sticky note ✏️ icon (pattern-matched) ────────────────────
    if isinstance(triggered, dict) and triggered.get("type") == "ann-edit-btn":
        # Pattern callbacks fire when new sticky-note buttons mount; require
        # an actual click somewhere before opening.
        if not any(c for c in (_edit_clicks or []) if c):
            return _empty_form_outputs()
        return _open_for_edit(triggered["id"])

    # ── Click on a chart's 📝 icon → edit mode ────────────────────────────
    if triggered in ("hh-chart", "daily-cost-chart"):
        click_data = hh_click if triggered == "hh-chart" else daily_click
        ann_id = _annotation_id_from_click(click_data)
        if ann_id is None:
            # Click was on a bar / area / blank — leave modal alone.
            return tuple(no_update for _ in range(14))
        return _open_for_edit(ann_id)

    # ── Cancel ───────────────────────────────────────────────────────────
    if triggered == "ann-mgr-cancel-btn":
        return _empty_form_outputs(is_open=False, error="")

    # ── Save ─────────────────────────────────────────────────────────────
    if triggered == "ann-mgr-save-btn":
        if account_id is None:
            return _empty_form_outputs(is_open=True, mode=mode_data,
                                       error="No active account.")
        try:
            period_start, period_end = _build_period(
                source, from_date, from_hour, from_minute,
                to_date, to_hour, to_minute,
            )
        except ValueError as e:
            return _empty_form_outputs(is_open=True, mode=mode_data, error=str(e))

        if not ((comment or "").strip() or tags):
            return _empty_form_outputs(
                is_open=True, mode=mode_data,
                error="Add a comment or at least one tag.",
            )

        try:
            if mode_data and mode_data.get("mode") == "edit" and mode_data.get("annotation_id"):
                annotations_service.update(
                    annotation_id=int(mode_data["annotation_id"]),
                    comment=(comment or "").strip() or None,
                    tag_names=tags or [],
                    period_start_utc=period_start,
                    period_end_utc=period_end,
                    source=source,
                )
            else:
                annotations_service.create(
                    account_id=account_id,
                    period_start_utc=period_start,
                    period_end_utc=period_end,
                    source=source,
                    comment=(comment or "").strip() or None,
                    tag_names=tags or [],
                )
        except Exception as e:
            return _empty_form_outputs(is_open=True, mode=mode_data, error=str(e))

        return (
            False,                                                       # is_open
            {"mode": "create", "annotation_id": None},                   # reset state
            no_update, no_update,
            no_update, no_update, no_update,
            no_update, no_update, no_update,
            no_update, no_update,
            "",
            (current_version or 0) + 1,
        )

    return _empty_form_outputs()


@callback(
    Output("ann-mgr-from-time-wrap", "style"),
    Output("ann-mgr-to-time-wrap",   "style"),
    Input("ann-mgr-source",          "value"),
)
def toggle_time_pickers(source: str | None):
    if source == "daily":
        hidden = {"display": "none"}
        return hidden, hidden
    visible = {"display": "flex", "alignItems": "center"}
    return visible, visible


@callback(
    Output("ann-mgr-tags", "options"),
    Input(stores.ANNOTATIONS_VERSION, "data"),
    Input(stores.DATA_VERSION,        "data"),
    Input("ann-mgr-tags",             "search_value"),
    State("ann-mgr-tags",             "value"),
)
def populate_mgr_tag_options(_av, _dv, search_value, current_value):
    df = tags_service.list_all()
    options = [{"label": row["name"], "value": row["name"]} for _, row in df.iterrows()]
    known = {opt["value"].lower() for opt in options}
    for v in current_value or []:
        if v and v.lower() not in known:
            options.append({"label": v, "value": v})
            known.add(v.lower())
    typed = (search_value or "").strip()
    if typed and typed.lower() not in known:
        options.append({"label": f'+ Create "{typed}"', "value": typed})
    return options


@callback(
    Output("ann-delete-confirm-modal",  "is_open"),
    Output("ann-pending-delete-id",     "data"),
    Output(stores.ANNOTATIONS_VERSION,  "data", allow_duplicate=True),
    Input({"type": "ann-delete-btn", "id": ALL}, "n_clicks"),
    Input("ann-delete-confirm-btn",     "n_clicks"),
    Input("ann-delete-cancel-btn",      "n_clicks"),
    State("ann-pending-delete-id",      "data"),
    State(stores.ANNOTATIONS_VERSION,   "data"),
    prevent_initial_call=True,
)
def manage_delete_modal(delete_clicks, _confirm_n, _cancel_n, pending_id, current_version):
    """Single-owner state machine: 🗑 → open confirm → confirm/cancel → close.

    Deletion happens only on confirm; ANNOTATIONS_VERSION bumps then so the
    board, chart overlays, and tag options refresh.
    """
    triggered = ctx.triggered_id

    # 🗑 on a sticky note → open modal, remember which annotation
    if isinstance(triggered, dict) and triggered.get("type") == "ann-delete-btn":
        if not any(c for c in (delete_clicks or []) if c):
            return no_update, no_update, no_update
        return True, int(triggered["id"]), no_update

    if triggered == "ann-delete-cancel-btn":
        return False, None, no_update

    if triggered == "ann-delete-confirm-btn":
        if pending_id is None:
            return False, None, no_update
        annotations_service.delete(int(pending_id))
        return False, None, (current_version or 0) + 1

    return no_update, no_update, no_update
