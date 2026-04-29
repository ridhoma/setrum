"""URL routing: swap `page-root` based on pathname.

The styleguide module is gitignored (local design-WIP only), so the import
is wrapped in a try/except — the app still works for anyone cloning fresh.
"""

from __future__ import annotations

from dash import Input, Output, callback

from dash_app import layout as layout_module

try:
    from dash_app import styleguide  # type: ignore[import-not-found]
    _HAS_STYLEGUIDE = True
except ImportError:
    _HAS_STYLEGUIDE = False


@callback(Output("page-root", "children"), Input("url", "pathname"))
def route(pathname: str | None):
    if pathname == "/styleguide" and _HAS_STYLEGUIDE:
        return styleguide.render()
    return layout_module.render_main()
