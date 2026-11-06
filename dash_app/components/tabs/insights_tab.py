"""Insights tab — Option 1: Editorial Field Notes.

III. Bottom-Up Appliance & Habit Attribution — Annotated Tag Ledger.
"""

from __future__ import annotations

from dash import html


def render() -> html.Div:
    section_head = html.Div(
        [
            html.Div(
                [
                    html.Div(
                        "III. Bottom-Up Appliance & Habit Attribution",
                        className="editorial-kicker",
                    ),
                    html.H1("Annotated Tag Ledger", className="editorial-h1"),
                ]
            ),
        ],
        className="editorial-section-head",
    )

    kpi_strip = html.Div(
        [
            html.Div(
                [
                    html.Div("Top Tagged Activity", className="kpi-label"),
                    html.Div("#cooking", className="kpi-value"),
                    html.Div("18.4 kWh across pinned sessions", className="kpi-sub"),
                ],
                className="kpi-cell hero",
            ),
            html.Div(
                [
                    html.Div("Avg Roast / Oven Session", className="kpi-label"),
                    html.Div("2.45 kWh", className="kpi-value"),
                    html.Div("£0.58 per meal cooked", className="kpi-sub"),
                ],
                className="kpi-cell",
            ),
            html.Div(
                [
                    html.Div('Phantom Baseline ("#away")', className="kpi-label"),
                    html.Div("1.82 kWh/d", className="kpi-value"),
                    html.Div("~76W continuous fridge + standby", className="kpi-sub"),
                ],
                className="kpi-cell",
            ),
            html.Div(
                [
                    html.Div("Unexplained Spikes", className="kpi-label"),
                    html.Div("3", className="kpi-value"),
                    html.Div("Click chart to inspect & annotate", className="kpi-sub"),
                ],
                className="kpi-cell",
            ),
        ],
        className="kpi-strip",
    )

    tag_card = html.Div(
        [
            html.H3("Cumulative Cost by Tag Vocabulary", className="mb-2", style={"fontFamily": "var(--setrum-font-display)"}),
            html.P("Aggregated directly from your half-hourly and daily field note annotations.", className="text-muted mb-4"),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Span([html.Strong("#cooking"), " (9 notes • avg 2.04 kWh)"]),
                                    html.Span(["18.4 kWh • ", html.Strong("£4.42")]),
                                ],
                                className="d-flex justify-content-between mb-1 font-monospace small",
                            ),
                            html.Div(
                                html.Div(style={"width": "72%", "height": "100%", "background": "var(--setrum-orange)", "borderRadius": "99px"}),
                                style={"height": "12px", "background": "var(--setrum-bg-surface-alt)", "borderRadius": "99px", "overflow": "hidden"},
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Span([html.Strong("#immersion-heater"), " (4 notes • 04:30 AM spike)"]),
                                    html.Span(["11.2 kWh • ", html.Strong("£2.69")]),
                                ],
                                className="d-flex justify-content-between mb-1 font-monospace small",
                            ),
                            html.Div(
                                html.Div(style={"width": "48%", "height": "100%", "background": "var(--setrum-cool)", "borderRadius": "99px"}),
                                style={"height": "12px", "background": "var(--setrum-bg-surface-alt)", "borderRadius": "99px", "overflow": "hidden"},
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Span([html.Strong("#laundry-dryer"), " (5 notes)"]),
                                    html.Span(["8.9 kWh • ", html.Strong("£2.14")]),
                                ],
                                className="d-flex justify-content-between mb-1 font-monospace small",
                            ),
                            html.Div(
                                html.Div(style={"width": "36%", "height": "100%", "background": "var(--setrum-accent)", "borderRadius": "99px"}),
                                style={"height": "12px", "background": "var(--setrum-bg-surface-alt)", "borderRadius": "99px", "overflow": "hidden"},
                            ),
                        ],
                        className="mb-3",
                    ),
                ],
            ),
        ],
        className="chart-card",
    )

    return html.Div([section_head, kpi_strip, tag_card])
