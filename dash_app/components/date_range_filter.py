"""Compact date range filter: a dropdown of preset windows + a collapsible
custom picker. Resolved range goes to a `dcc.Store` so chart callbacks
read a single source of truth.
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dcc, html


def _ids(prefix: str) -> dict[str, str]:
    return {
        "preset":   f"{prefix}-date-preset",
        "picker":   f"{prefix}-date-range",
        "wrap":     f"{prefix}-custom-wrap",
        "resolved": f"{prefix}-resolved-range",
    }


def render(
    prefix: str,
    presets: list[tuple[str, int]] | None = None,
    default_days: int = 30,
) -> html.Div:
    """Render a date range filter for the given `prefix`.

    `presets` is a list of (label, days) pairs. A "Custom" option is always
    appended. `default_days` should match one of the preset day counts.
    """
    if presets is None:
        presets = [("Last 7 days", 7), ("Last 14 days", 14), ("Last 30 days", 30)]

    ids = _ids(prefix)
    options = [{"label": label, "value": str(days)} for label, days in presets]
    options.append({"label": "Custom", "value": "custom"})

    return html.Div(
        [
            dbc.Select(
                id=ids["preset"],
                options=options,
                value=str(default_days),
                size="sm",
                class_name="date-range-select",
                # Survive tab swaps within the same browser session so user's
                # selection isn't reset every time the Consumptions tab remounts.
                persistence=True,
                persistence_type="session",
            ),
            html.Div(
                dcc.DatePickerRange(
                    id=ids["picker"],
                    display_format="YYYY-MM-DD",
                    className="mt-2",
                    persistence=True,
                    persistence_type="session",
                ),
                id=ids["wrap"],
                style={"display": "none"},
            ),
            dcc.Store(id=ids["resolved"]),
        ],
        className="date-range-filter",
    )


# Public so callbacks can reference IDs by structured lookup
ids = _ids
