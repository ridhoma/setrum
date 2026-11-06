"""Top-level Dash layout — Option 1: Editorial Field Notes.

The shell is `dcc.Location` + global stores + a `page-root` div whose
children are swapped by `callbacks/router.py` based on `pathname`:

  /            → main app (editorial masthead + workbench with field notes rail + modals)
  /styleguide  → design system preview (only present locally; the module
                 is gitignored — see `dash_app/styleguide.py`)

Stores live at this top level so they survive route swaps and so boot
callbacks always have somewhere to write.
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dcc, html

from dash_app import stores
from dash_app.components import (
    annotation_delete_confirm,
    annotation_form,
    annotation_manager_form,
    header,
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
            dcc.Store(id=stores.SHOW_PINS, data=True),
            html.Div(id="page-root"),
        ],
    )


def render_main() -> html.Div:
    """The full app shell — editorial masthead, workbench with main content + collapsible right rail, layout modals."""
    workbench = html.Div(
        [
            html.Main(
                [
                    html.Div(id="main-content"),
                    annotation_form.render(),
                    annotation_manager_form.render(),
                    annotation_delete_confirm.render(),
                ],
                className="setrum-content",
            ),
            html.Aside(
                [
                    html.Div(
                        [
                            html.Div("📌 Pinned Field Notes", className="rail-title"),
                            dbc.Button(
                                "+ Pin",
                                id="rail-new-btn",
                                className="btn-primary-editorial",
                                size="sm",
                            ),
                        ],
                        className="rail-header",
                    ),
                    html.Div(
                        [
                            dbc.Button(
                                [
                                    html.Span("👁️", id="rail-toggle-pins-icon", className="me-1"),
                                    html.Span("Hide All Pins", id="rail-toggle-pins-label"),
                                ],
                                id="rail-toggle-pins-btn",
                                className="btn-secondary-editorial btn-sm w-100 rail-toggle-pins-btn",
                                size="sm",
                                title="Show or hide annotation pins and bands on dashboard charts",
                            ),
                        ],
                        className="rail-toolbar",
                    ),
                    html.Div(
                        "Click ✏️ to edit or 🗑 to delete any pinned observation:",
                        className="rail-subtitle",
                    ),
                    html.Div(
                        id="rail-notes-list",
                        className="rail-notes-list",
                    ),
                ],
                id="field-notes-rail",
                className="field-notes-rail",
            ),
        ],
        id="workbench",
        className="setrum-workbench",
    )
    return html.Div(
        [header.render(), workbench],
        className="setrum-shell",
    )
