"""Insights tab: placeholder for now."""

from __future__ import annotations

from dash import html


def render() -> html.Div:
    return html.Div(
        [
            html.Div("✨", className="insights-placeholder-icon"),
            html.H3("Coming soon", className="text-muted text-center"),
            html.P(
                "Tag-based analytics, anomaly detection, "
                "appliance-level inference — once we have enough annotations to train on.",
                className="text-muted text-center",
                style={"maxWidth": "520px", "margin": "1rem auto"},
            ),
        ],
        className="text-center py-5",
    )
