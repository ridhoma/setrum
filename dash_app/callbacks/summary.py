"""Headline KPI cards.

Re-runs whenever DATA_VERSION bumps (sync just finished), the daily-chart
date filter changes, or the active account changes. The KPIs are scoped
to the daily chart's resolved range so they always reflect what the user
is currently looking at.
"""

from __future__ import annotations

from dash import Input, Output, callback

from core.services import consumption as consumption_service
from dash_app import stores


@callback(
    Output("summary-kwh",      "children"),
    Output("summary-cost",     "children"),
    Output("summary-price",    "children"),
    Output("summary-standing", "children"),
    Input(stores.DATA_VERSION,      "data"),
    Input("daily-resolved-range",   "data"),
    Input(stores.ACTIVE_ACCOUNT_ID, "data"),
)
def render_summary(_data_version, resolved, account_id):
    if not resolved or not resolved.get("start_date") or not resolved.get("end_date"):
        return "—", "—", "—", "—"
    m = consumption_service.get_summary_metrics(
        resolved["start_date"], resolved["end_date"], account_id=account_id
    )
    return (
        f"{m['total_kwh']:.1f} kWh",
        f"£{m['total_cost_inc_vat']:.2f}",
        f"{m['avg_price_exc_vat']:.1f}p / kWh",
        f"£{m['avg_standing_charge']:.2f} / day",
    )
