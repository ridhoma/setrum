"""Daily chart with view toggle (£ vs kWh) + BI-style date range filter.

`build_figure(daily_df, view)` is a pure function:
  * `view="cost"` → stacked bar (Standing Charge + Consumption Usage + VAT)
  * `view="kwh"`  → single bar of `consumption_kwh` (no VAT/SC breakdown,
    since kWh is meter-side and not subject to VAT)
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

from dash_app.charts import theme
from dash_app.components import date_range_filter, summary_cards
from dash_app.components.annotation_format import hover_text as _hover_text

# Stack roles, ordered bottom → top of the area.
#
# Each role uses a (fill, stroke) pair so the area reads as a soft wash
# while the stroke does the work of marking the trend. Pale fills also
# stop the stack from feeling like a wall of solid colour at large date
# ranges, which was the main complaint about the previous palette.
COLORS = {
    "Standing Charge":   (theme.WARNING_SOFT, theme.WARNING),  # gold wash + gold rule
    "Consumption Usage": (theme.ORANGE_SOFT,  theme.ORANGE),   # peach wash + Claude Orange
    "VAT":               (theme.INK_200,      theme.INK_300),  # neutral grey wash + rule
}
ORDER = ["Standing Charge", "Consumption Usage", "VAT"]
STROKE_WIDTH = 2.0


def _empty_figure(yaxis_title: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(**theme.base_layout(height=360, xaxis_title="", yaxis_title=yaxis_title))
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
        color = _first_color(ann.get("tag_colors")) or theme.ANNOTATION_DEFAULT_FILL
        shapes.append(
            dict(
                type="rect",
                xref="x", yref="paper",
                x0=ann["period_start_utc"],
                x1=ann["period_end_utc"],
                y0=0, y1=1,
                fillcolor=color,
                opacity=theme.ANNOTATION_FILL_OPACITY,
                line_width=0,
                layer="below",
            )
        )
    return shapes


def _fill(component: str) -> str:
    return COLORS[component][0]


def _stroke(component: str) -> str:
    return COLORS[component][1]


def _first_color(tag_colors: str | None) -> str | None:
    if not tag_colors:
        return None
    parts = [p for p in tag_colors.split("|") if p and p != "None"]
    return parts[0] if parts else None


def _annotation_icon_traces(annotations_df: pd.DataFrame | None, y_at: float) -> list[go.Scatter]:
    """A clickable 📝 icon at each annotation band's centre. Click → opens
    the manager modal in edit mode (handler in `annotation_manager.py`).
    """
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
            text=["📝"],
            textfont=dict(size=18),
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

    customdata = df["date"].dt.strftime("%a, %d %b %Y")
    fig = go.Figure()
    # Stacked area: each scatter trace fills up to the previous in stackgroup.
    # Points are at midnight UTC of each day — same x as annotation rect bounds,
    # so selection + overlay alignment stays exact.
    #
    # Each layer is a pale fill capped with a bolder stroke at the top edge —
    # so the eye reads the colour as a region but tracks the trend along the
    # stroke. `line.shape="spline"` would over-soften the daily cadence; we
    # keep the linear interpolation so day-to-day jumps stay visible.
    for component in ORDER:
        fig.add_scatter(
            name=component,
            x=df["date"],
            y=df[component],
            mode="lines",
            line=dict(width=STROKE_WIDTH, color=_stroke(component)),
            fillcolor=_fill(component),
            stackgroup="cost",
            customdata=customdata,
            hovertemplate=(
                "<b>%{customdata}</b><br>"
                f"{component}: £%{{y:.2f}}<extra></extra>"
            ),
        )

    fig.update_layout(**theme.base_layout(
        height=360,
        xaxis_title="", yaxis_title="Cost (£)",
        shapes=_monday_shapes(df["date"]) + _annotation_shapes(annotations_df),
        hovermode="x unified",
        dragmode="select",
        selectdirection="h",
        clickmode="event+select",
    ))
    fig.update_xaxes(**theme.xaxis_style(tickformat="%b %d"))
    fig.update_yaxes(**theme.yaxis_style(tickprefix="£"))
    # Hover-catcher traces for the annotation bands. y_max ≈ stacked total max.
    daily_total = (df["Standing Charge"] + df["Consumption Usage"] + df["VAT"]).max()
    y_max = float(daily_total or 0) * 1.05 or 1.0
    for trace in _annotation_icon_traces(annotations_df, y_max):
        fig.add_trace(trace)
    return fig


def _build_kwh_figure(daily_df: pd.DataFrame, annotations_df: pd.DataFrame | None = None) -> go.Figure:
    if daily_df.empty:
        return _empty_figure("kWh")

    df = daily_df.sort_values("date").copy()
    df["date"] = pd.to_datetime(df["date"])
    customdata = df["date"].dt.strftime("%a, %d %b %Y")

    fig = go.Figure()
    fig.add_scatter(
        name="Consumption",
        x=df["date"],
        y=df["consumption_kwh"],
        mode="lines",
        line=dict(width=STROKE_WIDTH, color=_stroke("Consumption Usage")),
        fillcolor=_fill("Consumption Usage"),
        fill="tozeroy",
        customdata=customdata,
        hovertemplate="<b>%{customdata}</b><br>%{y:.2f} kWh<extra></extra>",
    )
    fig.update_layout(**theme.base_layout(
        height=360,
        xaxis_title="", yaxis_title="kWh",
        showlegend=False,
        shapes=_monday_shapes(df["date"]) + _annotation_shapes(annotations_df),
        hovermode="x unified",
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


def render() -> html.Div:
    view_toggle = html.Div(
        dbc.RadioItems(
            id="daily-view-toggle",
            options=[
                {"label": "£",   "value": "cost"},
                {"label": "kWh", "value": "kwh"},
            ],
            value="cost",
            class_name="btn-group btn-group-sm",
            input_class_name="btn-check",
            label_class_name="btn btn-outline-secondary",
            label_checked_class_name="active",
        ),
        className="setrum-toggle",
    )

    return html.Div(
        [
            html.Div(
                [
                    html.H3("Daily Cost and Consumption", className="mb-0 flex-grow-1"),
                    view_toggle,
                    html.Div(
                        date_range_filter.render(
                            "daily",
                            presets=[
                                ("Last 7 days",  7),
                                ("Last 14 days", 14),
                                ("Last 30 days", 30),
                                ("Last 90 days", 90),
                            ],
                            default_days=30,
                        ),
                        className="ms-3",
                    ),
                ],
                className="d-flex align-items-center gap-2 mb-3",
            ),
            html.Div(summary_cards.render(), className="mb-3"),
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
                                "✏️",
                                id="daily-readout-edit",
                                color="link",
                                size="sm",
                                className="hh-readout-edit p-0 ms-2",
                                title="Annotate this selection",
                            ),
                        ],
                        id="daily-selection-readout",
                        className="hh-readout",
                        style={"display": "none"},
                    ),
                ],
                style={"position": "relative"},
            ),
        ]
    )
