"""Callback registration. Importing each submodule registers its callbacks
on the shared `app` instance via the @callback decorator.
"""

from dash_app.callbacks import (  # noqa: F401
    annotation_manager,
    annotations,
    boot,
    canvas,
    charts,
    date_filters,
    router,
    selection,
    summary,
    sync,
    tab_router,
)
