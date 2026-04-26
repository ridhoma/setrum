"""Setrum Dash entrypoint. `uv run python run.py`.

Initializes the schema (idempotent) and starts the Dash app on :8050.
The Streamlit app stays on :8501 until the cutover step.
"""

from __future__ import annotations

import argparse

from core.database import init_db
from dash_app import callbacks  # noqa: F401  -- registers all @callback decorators
from dash_app.app import app
from dash_app.layout import render as render_layout


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8050)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    init_db()
    app.layout = render_layout()
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
