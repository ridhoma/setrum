"""Compact date range filter — Option 1: Segmented Group + Collapsible Custom Range Picker.

Resolved range goes to a `dcc.Store` so chart callbacks read a single source of truth.
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
        presets = [("7D", 7), ("14D", 14), ("30D", 30), ("90D", 90)]

    ids = _ids(prefix)
    options = [{"label": label, "value": str(days)} for label, days in presets]
    options.append({"label": "Custom", "value": "custom"})

    return html.Div(
        [
            dbc.RadioItems(
                id=ids["preset"],
                options=options,
                value=str(default_days),
                class_name="segmented-group",
                input_class_name="btn-check",
                label_class_name="seg-btn",
                label_checked_class_name="active",
                persistence=True,
                persistence_type="session",
            ),
            html.Div(
                dcc.DatePickerRange(
                    id=ids["picker"],
                    display_format="YYYY-MM-DD",
                    persistence=True,
                    persistence_type="session",
                ),
                id=ids["wrap"],
                className="date-range-custom-wrap ms-2",
                style={"display": "none"},
            ),
            dcc.Store(id=ids["resolved"]),
        ],
        className="date-range-filter d-inline-flex align-items-center",
    )


ids = _ids
