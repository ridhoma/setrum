"""Top-level Dash layout: header on top, sidebar on left, main content
swaps based on the active tab.
"""

from __future__ import annotations

from dash import dcc, html

from dash_app import stores
from dash_app.components import (
    annotation_delete_confirm,
    annotation_form,
    annotation_manager_form,
    header,
    sidebar,
)


def render() -> html.Div:
    body = html.Div(
        [
            sidebar.render(),
            html.Main(
                [
                    # Hidden state stores
                    dcc.Store(id=stores.DATA_VERSION, data=0),
                    dcc.Store(id=stores.ANNOTATIONS_VERSION, data=0),
                    dcc.Store(id=stores.SELECTED_RANGE, data=None),
                    dcc.Store(id=stores.ACTIVE_ACCOUNT_ID, data=None),
                    dcc.Store(id=stores.SYNC_PROGRESS, data=None),
                    # Tab content host — populated by tab_router callback.
                    html.Div(id="main-content"),
                    # Floating annotation form (chart-bound) and manager modal
                    # live at the page level so they're available regardless
                    # of which tab is active.
                    annotation_form.render(),
                    annotation_manager_form.render(),
                    annotation_delete_confirm.render(),
                ],
                className="setrum-content",
            ),
        ],
        className="setrum-body",
    )

    return html.Div(
        [
            header.render(),
            body,
        ],
        className="setrum-shell",
    )
