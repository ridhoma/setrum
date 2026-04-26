"""Tab router: maps `main-tabs.value` → main-content children."""

from __future__ import annotations

from dash import Input, Output, callback

from dash_app.components.tabs import (
    annotations_tab,
    consumptions_tab,
    insights_tab,
)


@callback(
    Output("main-content", "children"),
    Input("main-tabs", "value"),
)
def render_tab(active_tab: str | None):
    if active_tab == "annotations":
        return annotations_tab.render()
    if active_tab == "insights":
        return insights_tab.render()
    return consumptions_tab.render()
