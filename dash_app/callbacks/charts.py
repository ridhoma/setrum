"""Chart-render callbacks. Each one re-runs whenever DATA_VERSION bumps,
ANNOTATIONS_VERSION bumps (overlay redraw), or the relevant date inputs
change. Date ranges come from the `date_range_filter` resolved stores so
this layer is unaware of preset-vs-custom logic.
"""

from __future__ import annotations

import datetime

from dash import Input, Output, callback

from core.services import annotations as annotations_service
from core.services import consumption as consumption_service
from dash_app import stores
from dash_app.components import daily_cost_chart, hh_chart


def _hh_window(start_date: str, end_date: str) -> tuple[str, str]:
    """Convert UI date strings to a `[start_utc, end_utc)` half-open window
    that includes the full end date.
    """
    start_utc = f"{start_date}T00:00:00"
    end_d = datetime.date.fromisoformat(end_date) + datetime.timedelta(days=1)
    end_utc = f"{end_d.isoformat()}T00:00:00"
    return start_utc, end_utc


@callback(
    Output("daily-cost-chart", "figure"),
    Input(stores.DATA_VERSION,        "data"),
    Input(stores.ANNOTATIONS_VERSION, "data"),
    Input("daily-resolved-range",     "data"),
    Input("daily-view-toggle",        "value"),
    Input(stores.ACTIVE_ACCOUNT_ID,   "data"),
)
def render_daily_cost(_dv: int, _av: int, resolved: dict | None, view: str | None, account_id: int | None):
    if not resolved or not resolved.get("start_date") or not resolved.get("end_date"):
        return daily_cost_chart.build_figure(
            consumption_service.get_daily_summary("1900-01-01", "1900-01-02"),
            view=view or "cost",
        )
    df = consumption_service.get_daily_summary(
        resolved["start_date"], resolved["end_date"], account_id=account_id
    )
    # Annotation overlays span the visible window; widen by 1 day on each side
    # so a band that started at 23:30 yesterday or ends at 00:30 tomorrow still
    # paints correctly against the daily bars.
    overlay_start = f"{resolved['start_date']}T00:00:00"
    overlay_end   = f"{resolved['end_date']}T23:59:59"
    overlays = annotations_service.list_in_range(
        overlay_start, overlay_end, account_id=account_id, source="daily"
    )
    return daily_cost_chart.build_figure(df, view=view or "cost", annotations_df=overlays)


@callback(
    Output("hh-chart", "figure"),
    Input(stores.DATA_VERSION, "data"),
    Input(stores.ANNOTATIONS_VERSION, "data"),
    Input("hh-resolved-range", "data"),
    Input(stores.ACTIVE_ACCOUNT_ID, "data"),
)
def render_hh_chart(_dv: int, _av: int, resolved: dict | None, account_id: int | None):
    if not resolved or not resolved.get("start_date") or not resolved.get("end_date"):
        return hh_chart.build_consumption_figure(
            consumption_service.get_half_hourly("1900-01-01", "1900-01-02")
        )
    start_utc, end_utc = _hh_window(resolved["start_date"], resolved["end_date"])
    df = consumption_service.get_half_hourly(start_utc, end_utc, account_id=account_id)
    overlays = annotations_service.list_in_range(
        start_utc, end_utc, account_id=account_id, source="half-hourly"
    )
    return hh_chart.build_consumption_figure(df, annotations_df=overlays)
