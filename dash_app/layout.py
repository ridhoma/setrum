"""Top-level Dash layout.

The shell is `dcc.Location` + global stores + a `page-root` div whose
children are swapped by `callbacks/router.py` based on `pathname`:

  /            → main app (header + sidebar + tabs + modals)
  /styleguide  → design system preview (only present locally; the module
                 is gitignored — see `dash_app/styleguide.py`)

Stores live at this top level so they survive route swaps and so boot
callbacks always have somewhere to write.
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
    return html.Div(
        [
            dcc.Location(id="url", refresh=False),
            # Global stores — always mounted, survive route swaps.
            dcc.Store(id=stores.DATA_VERSION, data=0),
            dcc.Store(id=stores.ANNOTATIONS_VERSION, data=0),
            dcc.Store(id=stores.SELECTED_RANGE, data=None),
            dcc.Store(id=stores.ACTIVE_ACCOUNT_ID, data=None),
            dcc.Store(id=stores.SYNC_PROGRESS, data=None),
            html.Div(id="page-root"),
        ],
    )


def render_main() -> html.Div:
    """The full app shell — header, sidebar, tab content host, layout-level modals."""
    body = html.Div(
        [
            sidebar.render(),
            html.Main(
                [
                    html.Div(id="main-content"),
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
        [header.render(), body],
        className="setrum-shell",
    )
