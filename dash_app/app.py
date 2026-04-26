"""Dash app instance. Imported by `run.py` and by the callbacks package.

The `DiskcacheManager` backs `@callback(background=True)` — required for
the non-blocking Refresh button. We hardcode `./.cache` (gitignored).
"""

from __future__ import annotations

import os

# macOS + Python 3.13 + fork() → workers exit immediately as <defunct>.
# `multiprocess` defaults to fork on Unix; force spawn so the background
# callback worker actually runs. Must happen before DiskcacheManager.
import multiprocess

try:
    multiprocess.set_start_method("spawn", force=True)
except RuntimeError:
    pass

import dash_bootstrap_components as dbc
import diskcache
from dash import Dash, DiskcacheManager

CACHE_DIR = os.environ.get("SETRUM_CACHE_DIR", "./.cache")

_cache = diskcache.Cache(CACHE_DIR)
background_callback_manager = DiskcacheManager(_cache)

app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.FLATLY],
    background_callback_manager=background_callback_manager,
    suppress_callback_exceptions=True,
    title="Setrum Analyser",
)

# Flask server handle, in case we ever want to run it under gunicorn etc.
server = app.server
