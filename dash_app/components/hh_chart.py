"""Half-hourly consumption chart with brush + annotation overlays.

The unit-price line was removed because Octopus's standard tariff is
near-flat and the chart added no information beyond the bar tooltips.
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

from dash_app.charts import theme
from dash_app.components import date_range_filter
from dash_app.components.annotation_format import hover_text as _hover_text


def _annotation_icon_traces(annotations_df: pd.DataFrame | None, y_at: float) -> list[go.Scatter]:
    """A clickable 📝 icon at the top-centre of each annotation band.

    Plotly shapes can't fire click or hover events, so we drop a tiny
    text marker at the band's centre that *can*. `customdata=[id]` makes
    the click handler look up the annotation; the hovertemplate shows
    the same period/comment/tags users see on the sticky.
    """
    if annotations_df is None or annotations_df.empty:
        return []
    traces: list[go.Scatter] = []
    for _, ann in annotations_df.iterrows():
        ann_id = int(ann["id"])
        ps = pd.to_datetime(ann["period_start_utc"])
        pe = pd.to_datetime(ann["period_end_utc"])
        x_center = ps + (pe - ps) / 2
        text = _hover_text(ann)
        traces.append(go.Scatter(
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
    return traces


def build_consumption_figure(
    hh_df: pd.DataFrame,
    annotations_df: pd.DataFrame | None = None,
) -> go.Figure:
    fig = go.Figure()
    if hh_df.empty:
        fig.update_layout(**theme.base_layout(height=360, xaxis_title="", yaxis_title="kWh"))
        fig.update_xaxes(**theme.xaxis_style())
        fig.update_yaxes(**theme.yaxis_style())
        return fig

    df = hh_df.sort_values("interval_start_at_utc").copy()
    df["interval_start_at_utc"] = pd.to_datetime(df["interval_start_at_utc"])

    fig.add_bar(
        x=df["interval_start_at_utc"],
        y=df["consumption_kwh"],
        marker_color=theme.DATA_PRIMARY,
        marker_line_width=0,
        # x is the bucket start. By default Plotly centres bars on x and
        # auto-derives width from data spacing. With offset=0 the bar's left
        # edge sits at x, and an explicit width of 30 min in ms means the
        # bar spans exactly [x, x+30min) — the same window used for the
        # annotation rect, so they line up to the pixel.
        offset=0,
        width=30 * 60 * 1000,
        customdata=df[["consumption_pence_exc_vat", "consumption_pence_inc_vat"]].to_numpy(),
        hovertemplate=(
            "<b>%{x|%a, %d %b %Y %H:%M}</b><br>"
            "Consumption: %{y:.4f} kWh<br>"
            "Cost excl. VAT: %{customdata[0]:.2f}p<br>"
            "Cost incl. VAT: %{customdata[1]:.2f}p"
            "<extra></extra>"
        ),
    )

    days = pd.to_datetime(df["interval_start_at_utc"].dt.date.unique())
    shapes = [theme.day_separator_shape(d) for d in days]

    if annotations_df is not None and not annotations_df.empty:
        for _, ann in annotations_df.iterrows():
            color = _first_color(ann.get("tag_colors")) or theme.ANNOTATION_DEFAULT_FILL
            shapes.append(
                dict(
                    type="rect",
                    xref="x",
                    yref="paper",
                    x0=ann["period_start_utc"],
                    x1=ann["period_end_utc"],
                    y0=0, y1=1,
                    fillcolor=color,
                    opacity=theme.ANNOTATION_FILL_OPACITY,
                    line_width=0,
                    layer="below",
                )
            )

    fig.update_layout(**theme.base_layout(
        height=360,
        xaxis_title="", yaxis_title="kWh",
        showlegend=False,
        shapes=shapes,
        bargap=0.05,
        dragmode="select",
        selectdirection="h",
        clickmode="event+select",
    ))
    fig.update_xaxes(**theme.xaxis_style(tickformat="%b %d, %H:%M"))
    fig.update_yaxes(**theme.yaxis_style())

    # Clickable annotation icon at the top of each band.
    y_max = float(df["consumption_kwh"].max() or 0) * 1.05 or 1.0
    for trace in _annotation_icon_traces(annotations_df, y_max):
        fig.add_trace(trace)
    return fig


def _first_color(tag_colors: str | None) -> str | None:
    if not tag_colors:
        return None
    parts = [p for p in tag_colors.split("|") if p and p != "None"]
    return parts[0] if parts else None


def render() -> html.Div:
    return html.Div(
        [
            dbc.Row(
                [
                    dbc.Col(html.H4("Half-Hourly Depth Profile"), md=6),
                    dbc.Col(
                        date_range_filter.render(
                            "hh",
                            presets=[
                                ("Last 3 days", 3),
                                ("Last 7 days", 7),
                                ("Last 14 days", 14),
                            ],
                            default_days=3,
                        ),
                        md=6,
                    ),
                ],
                className="align-items-center mb-2",
            ),
            html.Small("Half-Hourly Consumption (kWh)", className="text-muted"),
            html.Div(
                [
                    dcc.Graph(
                        id="hh-chart",
                        config={
                            "displaylogo": False,
                            "modeBarButtonsToAdd": ["select2d"],
                        },
                    ),
                    # Live readout overlay (top-left), populated by prefill_annotation_form.
                    # Carries the edit icon that opens the floating annotation form.
                    html.Div(
                        [
                            html.Span(id="hh-readout-text"),
                            dbc.Button(
                                "✏️",
                                id="hh-readout-edit",
                                color="link",
                                size="sm",
                                className="hh-readout-edit p-0 ms-2",
                                title="Annotate this selection",
                            ),
                        ],
                        id="hh-selection-readout",
                        className="hh-readout",
                        style={"display": "none"},
                    ),
                ],
                style={"position": "relative"},
            ),
        ]
    )
