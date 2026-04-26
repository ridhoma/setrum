"""Boot-time callbacks: populate `ACTIVE_ACCOUNT_ID` and the data-extent caption.

The active account is the first row in `source_accounts` whose
`moved_out_at IS NULL` — matches the filter used by `get_active_meters`.
"""

from __future__ import annotations

from dash import Input, Output, callback

from core.database import get_connection
from core.services import consumption as consumption_service
from dash_app import stores


@callback(
    Output(stores.ACTIVE_ACCOUNT_ID, "data"),
    Input(stores.DATA_VERSION, "data"),
)
def populate_active_account(_data_version: int) -> int | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT account_id FROM source_accounts WHERE moved_out_at IS NULL ORDER BY account_id LIMIT 1"
        ).fetchone()
    return int(row["account_id"]) if row else None


@callback(
    Output("data-extent-caption", "children"),
    Input(stores.DATA_VERSION, "data"),
    Input(stores.ACTIVE_ACCOUNT_ID, "data"),
)
def render_extent_caption(_data_version: int, account_id: int | None) -> str:
    extent = consumption_service.get_data_extent(account_id=account_id)
    if not extent.get("hh_max"):
        return "No data yet — click Refresh to sync."
    return (
        "Powered by Octopus Energy Agile API · "
        f"latest data: {extent['hh_max']} (UTC)"
    )
