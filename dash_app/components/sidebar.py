"""Sidebar component — retired in Option 1: Editorial Field Notes.

Sync and data status controls have been elevated to the top editorial masthead.
This module is retained for backward compatibility.
"""

from __future__ import annotations

from dash import html


def render() -> html.Div:
    """Empty placeholder — sidebar controls moved to top masthead."""
    return html.Div(style={"display": "none"})
