"""Callbacks that drive the reusable `date_range_filter` component.

Two pairs are registered: one for the daily chart (prefix `daily`) and one
for the half-hourly chart (prefix `hh`). Each pair contains:

  * `init_picker_bounds_*` — sets min/max + initial start/end on the picker
    when data extent changes. Runs once after each sync.

  * `resolve_range_*` — reads (preset, custom picker values) and publishes
    `{start_date, end_date}` to the resolved-range store + toggles the
    visibility of the custom picker wrap.
"""

from __future__ import annotations

import datetime

from dash import Input, Output, callback, no_update

from core.services import consumption as consumption_service
from dash_app import stores
from dash_app.components.date_range_filter import ids as filter_ids


def _resolve(preset: str, custom_start: str | None, custom_end: str | None, account_id: int | None):
    extent = consumption_service.get_data_extent(account_id=account_id)
    if not extent.get("daily_max") or not extent.get("daily_min"):
        return None, {"display": "none"}

    daily_min = datetime.date.fromisoformat(extent["daily_min"])
    daily_max = datetime.date.fromisoformat(extent["daily_max"])

    if preset == "custom":
        # Trust the picker; fall back to a sane window if it hasn't been set
        return (
            {
                "start_date": custom_start or daily_min.isoformat(),
                "end_date":   custom_end   or daily_max.isoformat(),
            },
            {"display": "block", "marginTop": "0.5rem"},
        )

    try:
        days = int(preset)
    except (TypeError, ValueError):
        days = 30
    start = max(daily_max - datetime.timedelta(days=days - 1), daily_min)
    return (
        {"start_date": start.isoformat(), "end_date": daily_max.isoformat()},
        {"display": "none"},
    )


def _picker_bounds(account_id: int | None):
    extent = consumption_service.get_data_extent(account_id=account_id)
    daily_min, daily_max = extent.get("daily_min"), extent.get("daily_max")
    if not daily_min or not daily_max:
        return no_update, no_update
    return daily_min, daily_max


def _preset_range(preset: str | None, account_id: int | None):
    """(start, end) ISO dates that a numeric preset ('7', '14', …) resolves
    to right now. Returns (no_update, no_update) for 'custom' / None / bad
    inputs / no data extent — callers use that to leave the picker alone."""
    if preset is None or preset == "custom":
        return no_update, no_update
    try:
        days = int(preset)
    except (TypeError, ValueError):
        return no_update, no_update
    extent = consumption_service.get_data_extent(account_id=account_id)
    daily_min, daily_max = extent.get("daily_min"), extent.get("daily_max")
    if not daily_min or not daily_max:
        return no_update, no_update
    daily_min_d = datetime.date.fromisoformat(daily_min)
    daily_max_d = datetime.date.fromisoformat(daily_max)
    start = max(daily_max_d - datetime.timedelta(days=days - 1), daily_min_d)
    return start.isoformat(), daily_max_d.isoformat()


# ─── daily ──────────────────────────────────────────────────────────────────
_daily = filter_ids("daily")


# Bounds (min/max) refresh on every mount so the picker rejects out-of-range
# dates. They are NOT persisted by Dash, so the bounds callback has no
# prevent_initial_call.
@callback(
    Output(_daily["picker"], "min_date_allowed"),
    Output(_daily["picker"], "max_date_allowed"),
    Input(stores.DATA_VERSION, "data"),
    Input(stores.ACTIVE_ACCOUNT_ID, "data"),
)
def init_daily_picker_bounds(_dv: int, account_id: int | None):
    return _picker_bounds(account_id)


# Mirror the active preset's range into the picker inputs. Fires on:
#   - first account resolution (ACTIVE_ACCOUNT_ID None → real)
#   - any preset change (e.g. user picks "Last 14 days")
#   - data refresh (DATA_VERSION bumps so daily_max may have advanced)
# When the preset is "custom", the helper returns no_update so the user's
# manually-picked dates aren't clobbered. prevent_initial_call=True keeps
# Dash's session persistence intact across tab remounts.
@callback(
    Output(_daily["picker"], "start_date"),
    Output(_daily["picker"], "end_date"),
    Input(_daily["preset"],         "value"),
    Input(stores.DATA_VERSION,      "data"),
    Input(stores.ACTIVE_ACCOUNT_ID, "data"),
    prevent_initial_call=True,
)
def sync_daily_picker_to_preset(preset, _dv, account_id):
    return _preset_range(preset, account_id)


@callback(
    Output(_daily["resolved"], "data"),
    Output(_daily["wrap"], "style"),
    Input(_daily["preset"], "value"),
    Input(_daily["picker"], "start_date"),
    Input(_daily["picker"], "end_date"),
    Input(stores.DATA_VERSION, "data"),
    Input(stores.ACTIVE_ACCOUNT_ID, "data"),
)
def resolve_daily(preset, custom_start, custom_end, _dv, account_id):
    return _resolve(preset, custom_start, custom_end, account_id)


# ─── half-hourly ────────────────────────────────────────────────────────────
_hh = filter_ids("hh")


@callback(
    Output(_hh["picker"], "min_date_allowed"),
    Output(_hh["picker"], "max_date_allowed"),
    Input(stores.DATA_VERSION, "data"),
    Input(stores.ACTIVE_ACCOUNT_ID, "data"),
)
def init_hh_picker_bounds(_dv: int, account_id: int | None):
    return _picker_bounds(account_id)


@callback(
    Output(_hh["picker"], "start_date"),
    Output(_hh["picker"], "end_date"),
    Input(_hh["preset"],            "value"),
    Input(stores.DATA_VERSION,      "data"),
    Input(stores.ACTIVE_ACCOUNT_ID, "data"),
    prevent_initial_call=True,
)
def sync_hh_picker_to_preset(preset, _dv, account_id):
    return _preset_range(preset, account_id)


@callback(
    Output(_hh["resolved"], "data"),
    Output(_hh["wrap"], "style"),
    Input(_hh["preset"], "value"),
    Input(_hh["picker"], "start_date"),
    Input(_hh["picker"], "end_date"),
    Input(stores.DATA_VERSION, "data"),
    Input(stores.ACTIVE_ACCOUNT_ID, "data"),
)
def resolve_hh(preset, custom_start, custom_end, _dv, account_id):
    return _resolve(preset, custom_start, custom_end, account_id)
