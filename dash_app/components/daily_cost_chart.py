"""Daily chart with stacked vertical bars (£ vs kWh) — Option 1: Editorial Field Notes.

`build_figure(daily_df, view)`:
  * `view="cost"` → stacked bars (Standing Charge + Consumption Usage + VAT)
  * `view="kwh"`  → single vertical bar of `consumption_kwh`
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

from dash_app.charts import theme
from dash_app.components.annotation_format import hover_text as _hover_text

# Colors matching Option 1 palette
COLORS = {
    "Standing Charge":   theme.COOL,       # Deep Petrol Teal
    "Consumption Usage": theme.ORANGE,     # Terracotta Vermilion
    "VAT":               theme.PEACH,      # Warm Peach
}
ORDER = ["Standing Charge", "Consumption Usage", "VAT"]


def _empty_figure(yaxis_title: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(**theme.base_layout(height=320, xaxis_title="", yaxis_title=yaxis_title))
    fig.update_xaxes(**theme.xaxis_style())
    fig.update_yaxes(**theme.yaxis_style())
    return fig


def _monday_shapes(dates: pd.Series) -> list[dict]:
    mondays = dates.loc[dates.dt.dayofweek == 0]
    return [theme.day_separator_shape(d) for d in mondays]


def _annotation_shapes(annotations_df: pd.DataFrame | None) -> list[dict]:
    if annotations_df is None or annotations_df.empty:
        return []
    shapes = []
    for _, ann in annotations_df.iterrows():
        shapes.append(
            dict(
                type="rect",
                xref="x", yref="paper",
                x0=ann["period_start_utc"],
                x1=ann["period_end_utc"],
                y0=0, y1=1,
                fillcolor="rgba(244, 211, 94, 0.34)",
                line=dict(color="#D4B130", width=1),
                layer="below",
            )
        )
    return shapes


def _annotation_icon_traces(annotations_df: pd.DataFrame | None, y_at: float) -> list[go.Scatter]:
    """Clickable 📌 icon at each annotation band's centre."""
    if annotations_df is None or annotations_df.empty:
        return []
    out: list[go.Scatter] = []
    for _, ann in annotations_df.iterrows():
        ann_id = int(ann["id"])
        ps = pd.to_datetime(ann["period_start_utc"])
        pe = pd.to_datetime(ann["period_end_utc"])
        x_center = ps + (pe - ps) / 2
        text = _hover_text(ann)
        out.append(go.Scatter(
            x=[x_center],
            y=[y_at],
            mode="text",
            text=["📌"],
            textfont=dict(size=14),
            customdata=[ann_id],
            hovertemplate=text + "<extra></extra>",
            showlegend=False,
            name="",
        ))
    return out


def build_figure(
    daily_df: pd.DataFrame,
    view: str = "cost",
    annotations_df: pd.DataFrame | None = None,
) -> go.Figure:
    if view == "kwh":
        return _build_kwh_figure(daily_df, annotations_df)
    return _build_cost_figure(daily_df, annotations_df)


def _build_cost_figure(daily_df: pd.DataFrame, annotations_df: pd.DataFrame | None = None) -> go.Figure:
    if daily_df.empty:
        return _empty_figure("Cost (£)")

    df = daily_df.sort_values("date").copy()
    df["date"] = pd.to_datetime(df["date"])
    df["Standing Charge"]   = df["standing_charge_pence_exc_vat"] / 100
    df["Consumption Usage"] = df["consumption_pence_exc_vat"] / 100
    df["VAT"]               = df["total_pence_vat"] / 100
    df["Total"]             = df["Standing Charge"] + df["Consumption Usage"] + df["VAT"]

    fig = go.Figure()

    # Stacked vertical bars — offset=8% of day, width=84% of day so each bar
    # sits inside [00:00, 24:00) with a clean 16% gap and aligns pixel-perfectly
    # with Monday 00:00 separators and [period_start_utc, period_end_utc) bands.
    day_ms = 86400 * 1000
    for component in ORDER:
        fig.add_bar(
            name=component,
            x=df["date"],
            y=df[component],
            offset=int(0.08 * day_ms),
            width=int(0.84 * day_ms),
            marker=dict(
                color=COLORS[component],
                cornerradius=2,
                line=dict(width=0),
            ),
            customdata=df["Total"],
            hovertemplate=(
                f"<b>%{{x|%a, %d %b %Y}}</b><br>"
                f"{component}: £%{{y:.2f}}<br>"
                f"Total Cost: £%{{customdata:.2f}}<extra></extra>"
            ),
        )

    fig.update_layout(**theme.base_layout(
        height=320,
        xaxis_title="", yaxis_title="Cost (£)",
        barmode="stack",
        bargap=0.18,
        showlegend=False,
        shapes=_monday_shapes(df["date"]) + _annotation_shapes(annotations_df),
        hovermode="closest",
        dragmode="select",
        selectdirection="h",
        clickmode="event+select",
    ))
    fig.update_xaxes(**theme.xaxis_style(tickformat="%b %d"))
    fig.update_yaxes(**theme.yaxis_style(tickprefix="£"))

    daily_total = df["Total"].max()
    y_max = float(daily_total or 0) * 1.05 or 1.0
    for trace in _annotation_icon_traces(annotations_df, y_max):
        fig.add_trace(trace)
    return fig


def _build_kwh_figure(daily_df: pd.DataFrame, annotations_df: pd.DataFrame | None = None) -> go.Figure:
    if daily_df.empty:
        return _empty_figure("kWh")

    df = daily_df.sort_values("date").copy()
    df["date"] = pd.to_datetime(df["date"])

    day_ms = 86400 * 1000
    fig = go.Figure()
    fig.add_bar(
        name="Consumption",
        x=df["date"],
        y=df["consumption_kwh"],
        offset=int(0.08 * day_ms),
        width=int(0.84 * day_ms),
        marker=dict(
            color=theme.DATA_PRIMARY,
            cornerradius=2,
            line=dict(width=0),
        ),
        hovertemplate=(
            "<b>%{x|%a, %d %b %Y}</b><br>"
            "Consumption: %{y:.2f} kWh<extra></extra>"
        ),
    )
    fig.update_layout(**theme.base_layout(
        height=320,
        xaxis_title="", yaxis_title="kWh",
        bargap=0.18,
        showlegend=False,
        shapes=_monday_shapes(df["date"]) + _annotation_shapes(annotations_df),
        hovermode="closest",
        dragmode="select",
        selectdirection="h",
        clickmode="event+select",
    ))
    fig.update_xaxes(**theme.xaxis_style(tickformat="%b %d"))
    fig.update_yaxes(**theme.yaxis_style())
    y_max = float(df["consumption_kwh"].max() or 0) * 1.05 or 1.0
    for trace in _annotation_icon_traces(annotations_df, y_max):
        fig.add_trace(trace)
    return fig


def legend_items(view: str = "cost", show_pins: bool = True) -> list:
    items = []
    if view == "kwh":
        items.append(
            html.Span(
                [html.Span(className="legend-swatch", style={"background": theme.ORANGE}), "Consumption Energy"],
                className="legend-item",
            )
        )
    else:
        items.extend(
            [
                html.Span(
                    [html.Span(className="legend-swatch", style={"background": theme.ORANGE}), "Consumption Usage"],
                    className="legend-item",
                ),
                html.Span(
                    [html.Span(className="legend-swatch", style={"background": theme.COOL}), "Standing Charge"],
                    className="legend-item",
                ),
                html.Span(
                    [html.Span(className="legend-swatch", style={"background": theme.PEACH}), "VAT (5%)"],
                    className="legend-item",
                ),
            ]
        )
    if show_pins:
        items.append(
            html.Span(
                [html.Span(className="legend-swatch", style={"background": theme.WARNING}), "Pinned Note"],
                className="legend-item",
            )
        )
    return items


def render() -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.H3("Daily Cost Stacked Breakdown (£)", id="daily-chart-title", className="mb-0"),
                            html.P("Track day-to-day bill drivers and weekend vs. weekday patterns — drag across any multi-day anomaly to total its cost and pin a note", className="text-muted small mb-0"),
                        ],
                        className="chart-title-wrap flex-grow-1",
                    ),
                    html.Div(
                        legend_items("cost"),
                        id="daily-legend",
                        className="chart-legend",
                    ),
                ],
                className="chart-card-header",
            ),
            html.Div(
                [
                    dcc.Graph(
                        id="daily-cost-chart",
                        config={
                            "displaylogo": False,
                            "modeBarButtonsToAdd": ["select2d"],
                        },
                    ),
                    html.Div(
                        [
                            html.Span(id="daily-readout-text"),
                            dbc.Button(
                                "✏️ Pin Note",
                                id="daily-readout-edit",
                                color="link",
                                size="sm",
                                className="brush-readout-btn ms-2",
                                title="Annotate this selection",
                            ),
                        ],
                        id="daily-selection-readout",
                        className="hh-readout brush-readout",
                        style={"display": "none"},
                    ),
                ],
                style={"position": "relative"},
            ),
        ],
        className="chart-card",
    )
