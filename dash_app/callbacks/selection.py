"""Brush capture + annotation form prefill, shared across HH and daily charts.

`SELECTED_RANGE` carries `{start, end, source}` where source is "hh" or
"daily". The prefill callback formats the readout differently per source
(date-only for daily, datetime for HH) and shows only the readout that
matches the source.
"""

from __future__ import annotations

import pandas as pd
from dash import Input, Output, State, callback, clientside_callback, ctx

from core.services import consumption as consumption_service
from core.services import tags as tags_service
from dash_app import stores

HH_BUCKET_FREQ   = "30min"
HH_BUCKET_DELTA  = pd.Timedelta(minutes=30)
DAY_BUCKET_FREQ  = "1D"
DAY_BUCKET_DELTA = pd.Timedelta(days=1)


def _to_utc_ts(value) -> pd.Timestamp:
    """Coerce a Plotly-emitted x value to a tz-aware UTC pandas Timestamp.

    Plotly may send dates as ISO strings, JS Date numbers (ms since epoch),
    or floats — `pd.to_datetime` defaults to nanoseconds for numerics, so
    we have to specify `unit='ms'` for those.
    """
    if isinstance(value, (int, float)):
        return pd.to_datetime(value, unit="ms", utc=True)
    return pd.to_datetime(value, utc=True)


def _extract_range(
    selected_data: dict | None,
    bucket_freq: str,
    bucket_delta: pd.Timedelta,
) -> dict | None:
    """Translate Plotly's `selectedData` to a half-open `[start, end)` window
    snapped to bucket boundaries — so every selection refers to actual data
    points, never to an interpolated mid-bucket position.

    Two reasons to floor/ceil aggressively:

      1. Bar traces with `offset=0, width=N` get visually centred on
         `x + N/2`, and Plotly's `selectedData.points[i].x` is that visual
         centre (e.g. 06:15 for the 06:00 HH bucket). Flooring brings it
         back to the data-point timestamp.
      2. `range.x` is pixel-interpolated. A click is essentially a
         zero-width range mid-bucket; without snapping the SQL window
         contains no bucket-starts and `SUM` returns 0.
    """
    if not selected_data:
        return None

    points = selected_data.get("points") or []
    xs = sorted([p["x"] for p in points if "x" in p], key=str)
    if xs:
        first = _to_utc_ts(xs[0]).floor(bucket_freq)
        last  = _to_utc_ts(xs[-1]).floor(bucket_freq) + bucket_delta
        return {"start": first.isoformat(), "end": last.isoformat()}

    rng = (selected_data.get("range") or {}).get("x")
    if rng and len(rng) >= 2:
        a_raw, b_raw = sorted([rng[0], rng[1]], key=str)
        a = _to_utc_ts(a_raw).floor(bucket_freq)
        b = _to_utc_ts(b_raw).ceil(bucket_freq)
        if a == b:                           # zero-width drag → 1 bucket wide
            b = a + bucket_delta
        return {"start": a.isoformat(), "end": b.isoformat()}
    return None


@callback(
    Output(stores.SELECTED_RANGE, "data"),
    Input("hh-chart", "selectedData"),
    prevent_initial_call=True,
)
def capture_hh_brush(selected_data: dict | None):
    rng = _extract_range(selected_data, HH_BUCKET_FREQ, HH_BUCKET_DELTA)
    return {**rng, "source": "half-hourly"} if rng else None


@callback(
    Output(stores.SELECTED_RANGE, "data", allow_duplicate=True),
    Input("daily-cost-chart", "selectedData"),
    prevent_initial_call=True,
)
def capture_daily_brush(selected_data: dict | None):
    rng = _extract_range(selected_data, DAY_BUCKET_FREQ, DAY_BUCKET_DELTA)
    return {**rng, "source": "daily"} if rng else None


def _fmt_hh(ts_iso: str) -> str:
    try:
        return pd.to_datetime(ts_iso).strftime("%a %d %b %H:%M")
    except (ValueError, TypeError):
        return ts_iso


def _fmt_day(ts_iso: str) -> str:
    try:
        return pd.to_datetime(ts_iso).strftime("%a %d %b")
    except (ValueError, TypeError):
        return ts_iso


@callback(
    Output("ann-period-display",      "children"),
    Output("ann-kwh-display",         "children"),
    Output("ann-cost-display",        "children"),
    Output("hh-readout-text",         "children"),
    Output("hh-selection-readout",    "style"),
    Output("daily-readout-text",      "children"),
    Output("daily-selection-readout", "style"),
    Input(stores.SELECTED_RANGE,    "data"),
    State(stores.ACTIVE_ACCOUNT_ID, "data"),
)
def prefill_annotation_form(rng: dict | None, account_id: int | None):
    """Populate the form fields and exactly one readout (the source chart).
    The form's *visibility* is owned by `toggle_annotation_form`.
    """
    hidden = {"display": "none"}
    if not rng:
        return "", "", "", "", hidden, "", hidden

    agg = consumption_service.aggregate_period(
        rng["start"], rng["end"], account_id=account_id
    )
    source = rng.get("source", "half-hourly")
    fmt = _fmt_hh if source == "half-hourly" else _fmt_day
    end_iso = rng["end"]
    # For daily, Plotly's bucket end is "next day 00:00" — display as the last
    # included day (end - 1s) so the user sees "Mon → Wed" not "Mon → Thu 00:00".
    end_label_iso = (
        (pd.to_datetime(end_iso) - pd.Timedelta(seconds=1)).isoformat()
        if source == "daily" else end_iso
    )

    # Collapse "Fri 03 Apr → Fri 03 Apr" to just "Fri 03 Apr" — same calendar
    # day on both ends means the selection is one whole day (or one HH bucket).
    start_ts = pd.to_datetime(rng["start"])
    end_label_ts = pd.to_datetime(end_label_iso)
    if source == "daily" and start_ts.date() == end_label_ts.date():
        period_label = _fmt_day(rng["start"])
    else:
        period_label = f"{fmt(rng['start'])} → {fmt(end_label_iso)}"
    kwh_label    = f"{agg['kwh']:.3f} kWh"
    cost_label   = f"£{agg['cost_pence_inc_vat'] / 100:.2f} (incl. VAT)"
    readout_text = f"{period_label}  ·  {kwh_label}  ·  £{agg['cost_pence_inc_vat'] / 100:.2f}"

    if source == "half-hourly":
        return period_label, kwh_label, cost_label, readout_text, {}, "", hidden
    return period_label, kwh_label, cost_label, "", hidden, readout_text, {}


# Form visibility + position: clientside so we can read the triggering
# readout's bounding rect and pin the form next to it (instead of always
# top-right of the page). Same trigger semantics as the previous Python
# callback — edit click opens, close/save/range-clear closes.
clientside_callback(
    """
    function(_hh, _daily, _close, _av, rng) {
        const ctx = window.dash_clientside.callback_context;
        if (!ctx.triggered || !ctx.triggered.length) return {display: 'none'};
        const id = ctx.triggered[0].prop_id.split('.')[0];
        if ((id === 'hh-readout-edit' || id === 'daily-readout-edit') && rng) {
            const readoutId = id === 'hh-readout-edit' ? 'hh-selection-readout' : 'daily-selection-readout';
            const readout = document.getElementById(readoutId);
            if (!readout) return {display: 'block'};
            const r = readout.getBoundingClientRect();
            const formW = 380, gap = 12;
            // Default: to the right of the readout, top-aligned.
            let left = r.right + gap;
            let top  = r.top;
            // If that overflows the right edge, fall back to placing
            // the form below the readout, left-aligned with it.
            if (left + formW > window.innerWidth - gap) {
                left = Math.max(gap, r.left);
                top  = r.bottom + gap;
            }
            return {
                display: 'block',
                top:  top  + 'px',
                left: left + 'px',
                right: 'auto',
            };
        }
        return {display: 'none'};
    }
    """,
    Output("ann-form-card", "style"),
    Input("hh-readout-edit",          "n_clicks"),
    Input("daily-readout-edit",       "n_clicks"),
    Input("ann-close-btn",            "n_clicks"),
    Input(stores.ANNOTATIONS_VERSION, "data"),
    Input(stores.SELECTED_RANGE,      "data"),
    prevent_initial_call=True,
)


@callback(
    Output("ann-save-btn", "disabled"),
    Input(stores.SELECTED_RANGE, "data"),
    Input("ann-comment",         "value"),
    Input("ann-tags",            "value"),
)
def toggle_save_button(rng: dict | None, comment: str | None, tags: list | None):
    if not rng:
        return True
    has_content = bool((comment or "").strip()) or bool(tags)
    return not has_content


@callback(
    Output("ann-tags", "options"),
    Input(stores.ANNOTATIONS_VERSION, "data"),
    Input(stores.DATA_VERSION,        "data"),
    Input("ann-tags",                 "search_value"),
    State("ann-tags",                 "value"),
)
def populate_tag_options(_av: int, _dv: int, search_value: str | None, current_value: list | None):
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
