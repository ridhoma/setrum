"""Setrum Dash entrypoint.

Can be run via:
  Dev:  `uv run python run.py`
  Prod: `uv run gunicorn "run:server" --bind 0.0.0.0:8050 --workers 2`
"""

from __future__ import annotations

import argparse
import os

from core.database import init_db
from core.services.sync import start_background_scheduler
from dash_app import callbacks  # noqa: F401  -- registers all @callback decorators
from dash_app.app import app, server
from dash_app.layout import render as render_layout

# Initialize database schema, layout, and background sync scheduler
init_db()
app.layout = render_layout()
start_background_scheduler()


@server.route("/health")
def health_check() -> tuple[dict[str, str], int]:
    """Lightweight health check endpoint for Docker / uptime monitors."""
    return {"status": "ok", "app": "setrum"}, 200


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8050")))
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
