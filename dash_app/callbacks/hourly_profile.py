"""Callbacks for 24-Hour Profile table and inline Preset / Calendar dropdown."""

from __future__ import annotations

import datetime

from dash import ALL, Input, Output, State, callback, ctx, no_update

from core.services import consumption as consumption_service
from dash_app import stores
from dash_app.components import hourly_profile_table
from dash_app.components.hourly_profile_table import format_preset_label, resolve_preset_dates


@callback(
    Output(stores.HOURLY_PRESET_1, "data"),
    Output(stores.HOURLY_PRESET_2, "data"),
    Input(stores.DATA_VERSION, "data"),
    Input(stores.ACTIVE_ACCOUNT_ID, "data"),
    State(stores.HOURLY_PRESET_1, "data"),
    State(stores.HOURLY_PRESET_2, "data"),
)
def init_hourly_presets(
    _dv: int,
    account_id: int | None,
    stored_p1: dict | None,
    stored_p2: dict | None,
):
    """Ensure Preset 1 and Preset 2 have sane defaults relative to latest available data."""
    extent = consumption_service.get_data_extent(account_id=account_id)
    hh_max = extent.get("hh_max")
    max_d = str(hh_max)[:10] if hh_max else None
    if not max_d:
        return no_update, no_update

    p1_out = no_update
    if not stored_p1 or not stored_p1.get("start_date") or not stored_p1.get("end_date"):
        p1_s, p1_e = resolve_preset_dates("7D", max_d)
        p1_out = {
            "preset": "7D",
            "start_date": p1_s,
            "end_date": p1_e,
            "label": "Last 7D",
        }

    p2_out = no_update
    if not stored_p2 or not stored_p2.get("start_date") or not stored_p2.get("end_date"):
        p2_s, p2_e = resolve_preset_dates("30D", max_d)
        p2_out = {
            "preset": "30D",
            "start_date": p2_s,
            "end_date": p2_e,
            "label": "Last 30D",
        }

    return p1_out, p2_out


@callback(
    Output("hourly-profile-tbody", "children"),
    Output("hourly-profile-tfoot", "children"),
    Output("hourly-preset-1-label", "children"),
    Output("hourly-preset-2-label", "children"),
    Input(stores.HOURLY_PRESET_1, "data"),
    Input(stores.HOURLY_PRESET_2, "data"),
    Input(stores.DATA_VERSION, "data"),
    Input(stores.ACTIVE_ACCOUNT_ID, "data"),
)
def render_hourly_profile_table(
    p1_data: dict | None,
    p2_data: dict | None,
    _dv: int,
    account_id: int | None,
):
    extent = consumption_service.get_data_extent(account_id=account_id)
    hh_max = extent.get("hh_max")
    max_d = str(hh_max)[:10] if hh_max else None

    # Fallback to defaults if stores not yet primed
    if p1_data and p1_data.get("start_date") and p1_data.get("end_date"):
        p1_s = p1_data["start_date"]
        p1_e = p1_data["end_date"]
        p1_lbl = p1_data.get("label") or format_preset_label(p1_data.get("preset"), p1_s, p1_e)
    elif max_d:
        p1_s, p1_e = resolve_preset_dates("7D", max_d)
        p1_lbl = "Last 7D"
    else:
        p1_s, p1_e, p1_lbl = None, None, "Preset 1"

    if p2_data and p2_data.get("start_date") and p2_data.get("end_date"):
        p2_s = p2_data["start_date"]
        p2_e = p2_data["end_date"]
        p2_lbl = p2_data.get("label") or format_preset_label(p2_data.get("preset"), p2_s, p2_e)
    elif max_d:
        p2_s, p2_e = resolve_preset_dates("30D", max_d)
        p2_lbl = "Last 30D"
    else:
        p2_s, p2_e, p2_lbl = None, None, "Preset 2"

    profile = consumption_service.get_hourly_profile_comparison(
        p1_start=p1_s,
        p1_end=p1_e,
        p2_start=p2_s,
        p2_end=p2_e,
        account_id=account_id,
    )
    tbody, tfoot = hourly_profile_table.render_rows_and_footer(profile)
    return tbody, tfoot, p1_lbl, p2_lbl


@callback(
    Output("hourly-preset-dropdown", "style"),
    Output("hourly-dropdown-title", "children"),
    Output(stores.HOURLY_MODAL_STATE, "data"),
    Output(stores.HOURLY_PRESET_1, "data", allow_duplicate=True),
    Output(stores.HOURLY_PRESET_2, "data", allow_duplicate=True),
    Input("hourly-preset-1-btn", "n_clicks"),
    Input("hourly-preset-2-btn", "n_clicks"),
    Input("hourly-dropdown-close-btn", "n_clicks"),
    Input("hourly-dropdown-cancel-btn", "n_clicks"),
    Input("hourly-dropdown-apply-btn", "n_clicks"),
    Input("hourly-opt-7D", "n_clicks"),
    Input("hourly-opt-14D", "n_clicks"),
    Input("hourly-opt-30D", "n_clicks"),
    Input("hourly-opt-90D", "n_clicks"),
    Input("hourly-opt-custom", "n_clicks"),
    Input("hourly-cal-prev-btn", "n_clicks"),
    Input("hourly-cal-next-btn", "n_clicks"),
    Input({"type": "hourly-cal-day", "date": ALL}, "n_clicks"),
    State("hourly-preset-dropdown", "style"),
    State("hourly-cal-input-start", "value"),
    State("hourly-cal-input-end", "value"),
    State(stores.HOURLY_MODAL_STATE, "data"),
    State(stores.HOURLY_PRESET_1, "data"),
    State(stores.HOURLY_PRESET_2, "data"),
    State(stores.ACTIVE_ACCOUNT_ID, "data"),
    prevent_initial_call=True,
)
def manage_hourly_preset_dropdown(
    p1_clicks: int | None,
    p2_clicks: int | None,
    _close_clicks: int | None,
    _cancel_clicks: int | None,
    _apply_clicks: int | None,
    _opt_7d: int | None,
    _opt_14d: int | None,
    _opt_30d: int | None,
    _opt_90d: int | None,
    _opt_custom: int | None,
    _prev_clicks: int | None,
    _next_clicks: int | None,
    _day_clicks: list[int | None],
    current_style: dict | None,
    start_val: str | None,
    end_val: str | None,
    modal_state: dict | None,
    stored_p1: dict | None,
    stored_p2: dict | None,
    account_id: int | None,
):
    trig = ctx.triggered_id
    if not trig:
        return no_update, no_update, no_update, no_update, no_update

    extent = consumption_service.get_data_extent(account_id=account_id)
    hh_min = extent.get("hh_min")
    hh_max = extent.get("hh_max")
    min_d = str(hh_min)[:10] if hh_min else None
    max_d = str(hh_max)[:10] if hh_max else datetime.date.today().isoformat()

    is_currently_open = (current_style or {}).get("display") == "block"

    # Open / Toggle Preset 1 Dropdown
    if trig == "hourly-preset-1-btn":
        if not p1_clicks:
            return no_update, no_update, no_update, no_update, no_update
        if is_currently_open and (modal_state or {}).get("target") == "p1":
            return {"display": "none"}, no_update, no_update, no_update, no_update

        cur_p1 = stored_p1 or {}
        p = cur_p1.get("preset", "7D")
        s = cur_p1.get("start_date")
        e = cur_p1.get("end_date")
        if not s or not e:
            s, e = resolve_preset_dates("7D", max_d)
            p = "7D"
        current_month = (e or max_d)[:7]
        state = {
            "target": "p1",
            "preset": p,
            "start_date": s,
            "end_date": e,
            "current_month": current_month,
            "min_date": min_d,
            "max_date": max_d,
            "selecting_end": False,
        }
        return {"display": "block", "left": "13%"}, "Preset 1 Period", state, no_update, no_update

    # Open / Toggle Preset 2 Dropdown
    if trig == "hourly-preset-2-btn":
        if not p2_clicks:
            return no_update, no_update, no_update, no_update, no_update
        if is_currently_open and (modal_state or {}).get("target") == "p2":
            return {"display": "none"}, no_update, no_update, no_update, no_update

        cur_p2 = stored_p2 or {}
        p = cur_p2.get("preset", "30D")
        s = cur_p2.get("start_date")
        e = cur_p2.get("end_date")
        if not s or not e:
            s, e = resolve_preset_dates("30D", max_d)
            p = "30D"
        current_month = (e or max_d)[:7]
        state = {
            "target": "p2",
            "preset": p,
            "start_date": s,
            "end_date": e,
            "current_month": current_month,
            "min_date": min_d,
            "max_date": max_d,
            "selecting_end": False,
        }
        return {"display": "block", "right": "12%"}, "Preset 2 Period", state, no_update, no_update

    # Close / Cancel button
    if trig in ("hourly-dropdown-close-btn", "hourly-dropdown-cancel-btn"):
        return {"display": "none"}, no_update, no_update, no_update, no_update

    # Apply button
    if trig == "hourly-dropdown-apply-btn":
        if not modal_state:
            return {"display": "none"}, no_update, no_update, no_update, no_update
        target = modal_state.get("target", "p1")
        preset = modal_state.get("preset", "custom")
        s = modal_state.get("start_date") or max_d
        e = modal_state.get("end_date") or max_d

        if preset == "custom" and start_val and end_val:
            try:
                datetime.date.fromisoformat(start_val)
                datetime.date.fromisoformat(end_val)
                s, e = start_val, end_val
            except ValueError:
                pass

        if s > e:
            s, e = e, s
        label = format_preset_label(preset, s, e)
        new_data = {
            "preset": preset,
            "start_date": s,
            "end_date": e,
            "label": label,
        }
        if target == "p1":
            return {"display": "none"}, no_update, no_update, new_data, no_update
        else:
            return {"display": "none"}, no_update, no_update, no_update, new_data

    # Preset shortcut options (7D, 14D, 30D, 90D)
    if isinstance(trig, str) and trig.startswith("hourly-opt-") and trig != "hourly-opt-custom":
        preset_code = trig.replace("hourly-opt-", "")
        bound_max = (modal_state.get("max_date") if modal_state else None) or max_d
        s, e = resolve_preset_dates(preset_code, bound_max)
        new_state = dict(modal_state or {})
        new_state.update(
            {
                "preset": preset_code,
                "start_date": s,
                "end_date": e,
                "current_month": e[:7],
                "selecting_end": False,
            }
        )
        return no_update, no_update, new_state, no_update, no_update

    # Custom preset button
    if trig == "hourly-opt-custom":
        new_state = dict(modal_state or {})
        new_state.update({"preset": "custom", "selecting_end": False})
        return no_update, no_update, new_state, no_update, no_update

    # Month navigation: Previous
    if trig == "hourly-cal-prev-btn":
        cur_ym = (modal_state.get("current_month") if modal_state else None) or max_d[:7]
        try:
            y, m = map(int, cur_ym.split("-"))
            prev_ym = f"{y-1}-12" if m == 1 else f"{y}-{m-1:02d}"
        except Exception:
            prev_ym = cur_ym
        new_state = dict(modal_state or {})
        new_state["current_month"] = prev_ym
        return no_update, no_update, new_state, no_update, no_update

    # Month navigation: Next
    if trig == "hourly-cal-next-btn":
        cur_ym = (modal_state.get("current_month") if modal_state else None) or max_d[:7]
        try:
            y, m = map(int, cur_ym.split("-"))
            next_ym = f"{y+1}-01" if m == 12 else f"{y}-{m+1:02d}"
        except Exception:
            next_ym = cur_ym
        new_state = dict(modal_state or {})
        new_state["current_month"] = next_ym
        return no_update, no_update, new_state, no_update, no_update

    # Calendar day clicked
    if isinstance(trig, dict) and trig.get("type") == "hourly-cal-day":
        clicked_date = trig.get("date")
        if not clicked_date:
            return no_update, no_update, no_update, no_update, no_update
        new_state = dict(modal_state or {})
        new_state["preset"] = "custom"
        if new_state.get("selecting_end"):
            # Second click of a custom range
            s_d = new_state.get("start_date")
            if s_d and clicked_date < s_d:
                new_state["start_date"] = clicked_date
                new_state["end_date"] = s_d
            else:
                new_state["end_date"] = clicked_date
            new_state["selecting_end"] = False
        else:
            # First click: begin range
            new_state["start_date"] = clicked_date
            new_state["end_date"] = clicked_date
            new_state["selecting_end"] = True
        return no_update, no_update, new_state, no_update, no_update

    return no_update, no_update, no_update, no_update, no_update


@callback(
    Output("hourly-opt-7D", "className"),
    Output("hourly-opt-14D", "className"),
    Output("hourly-opt-30D", "className"),
    Output("hourly-opt-90D", "className"),
    Output("hourly-opt-custom", "className"),
    Output("hourly-cal-month-heading", "children"),
    Output("hourly-cal-grid", "children"),
    Output("hourly-cal-summary", "children"),
    Output("hourly-cal-input-start", "value"),
    Output("hourly-cal-input-end", "value"),
    Input(stores.HOURLY_MODAL_STATE, "data"),
)
def render_modal_content(modal_state: dict | None):
    if not modal_state:
        base_opt = "hourly-preset-opt"
        return (
            base_opt,
            base_opt,
            base_opt,
            base_opt,
            base_opt,
            "",
            None,
            "",
            "",
            "",
        )

    preset = modal_state.get("preset", "7D")
    cls_7d = "hourly-preset-opt" + (" active" if preset == "7D" else "")
    cls_14d = "hourly-preset-opt" + (" active" if preset == "14D" else "")
    cls_30d = "hourly-preset-opt" + (" active" if preset == "30D" else "")
    cls_90d = "hourly-preset-opt" + (" active" if preset == "90D" else "")
    cls_custom = "hourly-preset-opt" + (" active" if preset == "custom" else "")

    cur_ym = modal_state.get("current_month") or "2026-11"
    try:
        y, m = map(int, cur_ym.split("-"))
        dt_month = datetime.datetime(y, m, 1)
        heading = dt_month.strftime("%B %Y")
    except Exception:
        y, m = 2026, 11
        heading = cur_ym

    s = modal_state.get("start_date")
    e = modal_state.get("end_date")
    min_d = modal_state.get("min_date")
    max_d = modal_state.get("max_date")

    grid = hourly_profile_table.render_calendar_grid(y, m, s, e, min_d, max_d)

    if s and e:
        try:
            s_dt = datetime.date.fromisoformat(s)
            e_dt = datetime.date.fromisoformat(e)
            if s_dt > e_dt:
                s_dt, e_dt = e_dt, s_dt
                s, e = s_dt.isoformat(), e_dt.isoformat()
            days_count = (e_dt - s_dt).days + 1
            summary = f"Selected: {s} to {e} ({days_count} {'day' if days_count == 1 else 'days'})"
        except ValueError:
            summary = f"Selected: {s} to {e}"
    else:
        summary = "Click calendar or choose a preset to select period"

    return (
        cls_7d,
        cls_14d,
        cls_30d,
        cls_90d,
        cls_custom,
        heading,
        grid,
        summary,
        s or "",
        e or "",
    )
