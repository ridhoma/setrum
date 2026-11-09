"""Daily chart with stacked vertical bars (£ vs kWh) — Option 1: Editorial Field Notes.

`build_figure(daily_df, view)`:
  * `view="cost"` → stacked bars (Standing Charge + Consumption Usage + VAT)
  * `view="kwh"`  → single vertical bar of `consumption_kwh`
"""

from __future__ import annotations

import calendar
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

from dash_app.charts import theme
from dash_app.components import date_range_filter
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
    granularity: str = "daily",
    annotations_df: pd.DataFrame | None = None,
) -> go.Figure:
    if view == "kwh":
        return _build_kwh_figure(daily_df, granularity, annotations_df)
    return _build_cost_figure(daily_df, granularity, annotations_df)


def _compute_month_forecast(df: pd.DataFrame) -> dict | None:
    """Compute month-end projection for the latest month if it is incomplete.

    Estimates remaining month consumption (kWh & £) by taking the last-30 days
    daily average multiplied by remaining days of the month.
    """
    if df.empty:
        return None

    latest_date = df["date"].max()
    year = latest_date.year
    month = latest_date.month
    total_days = calendar.monthrange(year, month)[1]

    month_mask = (df["date"].dt.year == year) & (df["date"].dt.month == month)
    month_df = df[month_mask]
    recorded_days = len(month_df["date"].dt.date.unique())

    if recorded_days >= total_days:
        return None  # Month is fully recorded, no forecast needed

    remaining_days = total_days - recorded_days
    if remaining_days <= 0:
        return None

    # Compute 30-day daily averages from the latest available 30 days
    last_30_df = df[df["date"] <= latest_date].tail(30)
    if last_30_df.empty:
        return None

    avg_daily_kwh = float(last_30_df["consumption_kwh"].mean() or 0.0)

    # Cost in £ (including VAT)
    if "total_pence_inc_vat" in last_30_df.columns:
        cost_series = last_30_df["total_pence_inc_vat"] / 100
    elif "Total" in last_30_df.columns:
        cost_series = last_30_df["Total"]
    else:
        cost_series = (last_30_df.get("consumption_pence_exc_vat", 0) + last_30_df.get("standing_charge_pence_exc_vat", 0)) / 100
    avg_daily_cost = float(cost_series.mean() or 0.0)

    current_kwh = float(month_df["consumption_kwh"].sum() or 0.0)
    if "total_pence_inc_vat" in month_df.columns:
        month_cost_series = month_df["total_pence_inc_vat"] / 100
    elif "Total" in month_df.columns:
        month_cost_series = month_df["Total"]
    else:
        month_cost_series = (month_df.get("consumption_pence_exc_vat", 0) + month_df.get("standing_charge_pence_exc_vat", 0)) / 100
    current_cost = float(month_cost_series.sum() or 0.0)

    forecast_kwh = avg_daily_kwh * remaining_days
    forecast_cost = avg_daily_cost * remaining_days

    date_series = latest_date.tz_localize(None) if latest_date.tz is not None else latest_date
    month_ts = date_series.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    return {
        "month_ts": month_ts,
        "recorded_days": recorded_days,
        "total_days": total_days,
        "remaining_days": remaining_days,
        "avg_daily_kwh": avg_daily_kwh,
        "avg_daily_cost": avg_daily_cost,
        "forecast_kwh": forecast_kwh,
        "forecast_cost": forecast_cost,
        "current_kwh": current_kwh,
        "current_cost": current_cost,
        "projected_kwh": current_kwh + forecast_kwh,
        "projected_cost": current_cost + forecast_cost,
    }


def _build_cost_figure(
    daily_df: pd.DataFrame,
    granularity: str = "daily",
    annotations_df: pd.DataFrame | None = None,
) -> go.Figure:
    if daily_df.empty:
        return _empty_figure("Cost (£)")

    df = daily_df.sort_values("date").copy()
    df["date"] = pd.to_datetime(df["date"])

    if granularity == "monthly":
        date_series = df["date"].dt.tz_localize(None) if df["date"].dt.tz is not None else df["date"]
        df["month"] = date_series.dt.to_period("M").dt.to_timestamp()
        m_df = df.groupby("month", as_index=False).agg({
            "standing_charge_pence_exc_vat": "sum",
            "consumption_pence_exc_vat": "sum",
            "total_pence_vat": "sum",
        })
        m_df["Standing Charge"]   = m_df["standing_charge_pence_exc_vat"] / 100
        m_df["Consumption Usage"] = m_df["consumption_pence_exc_vat"] / 100
        m_df["VAT"]               = m_df["total_pence_vat"] / 100
        m_df["Total"]             = m_df["Standing Charge"] + m_df["Consumption Usage"] + m_df["VAT"]

        fc = _compute_month_forecast(df)

        fig = go.Figure()
        month_ms = 24 * 86400 * 1000
        offset_ms = 3 * 86400 * 1000
        for component in ORDER:
            fig.add_bar(
                name=component,
                x=m_df["month"],
                y=m_df[component],
                offset=offset_ms,
                width=month_ms,
                marker=dict(
                    color=COLORS[component],
                    cornerradius=2,
                    line=dict(width=0),
                ),
                customdata=m_df["Total"],
                hovertemplate=(
                    f"<b>%{{x|%B %Y}}</b><br>"
                    f"{component}: £%{{y:.2f}}<br>"
                    f"Total Cost: £%{{customdata:.2f}}<extra></extra>"
                ),
            )

        forecast_shapes = []
        if fc is not None:
            fig.add_bar(
                name="Forecast (Est.)",
                x=[fc["month_ts"]],
                y=[fc["forecast_cost"]],
                offset=offset_ms,
                width=month_ms,
                marker=dict(
                    color="rgba(217, 93, 57, 0.08)",
                    line=dict(width=0),
                ),
                customdata=[[
                    fc["current_cost"],
                    fc["forecast_cost"],
                    fc["projected_cost"],
                    fc["recorded_days"],
                    fc["remaining_days"],
                    fc["avg_daily_cost"],
                ]],
                hovertemplate=(
                    "<b>%{x|%B %Y} (Month-End Forecast)</b><br>"
                    "Actual to Date (%{customdata[3]}d): £%{customdata[0]:.2f}<br>"
                    "Projected Rest of Month (%{customdata[4]}d): +£%{customdata[1]:.2f}<br>"
                    "<b>Est. Month Total: £%{customdata[2]:.2f}</b><br>"
                    "<span style='color:#7D7367'>Based on 30D avg: £%{customdata[5]:.2f}/day</span><extra></extra>"
                ),
            )
            x0 = fc["month_ts"] + pd.Timedelta(milliseconds=offset_ms)
            x1 = fc["month_ts"] + pd.Timedelta(milliseconds=offset_ms + month_ms)
            forecast_shapes.append(dict(
                type="rect",
                xref="x",
                yref="y",
                x0=x0,
                x1=x1,
                y0=fc["current_cost"],
                y1=fc["projected_cost"],
                line=dict(color=theme.ORANGE, width=1.5, dash="dash"),
                fillcolor="rgba(217, 93, 57, 0.06)",
            ))

        fig.update_layout(**theme.base_layout(
            height=320,
            xaxis_title="", yaxis_title="Cost (£)",
            barmode="stack",
            bargap=0.18,
            showlegend=False,
            shapes=_annotation_shapes(annotations_df) + forecast_shapes,
            hovermode="closest",
            dragmode="select",
            selectdirection="h",
            clickmode="event+select",
        ))
        fig.update_xaxes(**theme.xaxis_style(tickformat="%b %Y"))
        fig.update_yaxes(**theme.yaxis_style(tickprefix="£"))

        total_max = float(m_df["Total"].max() or 0)
        if fc is not None:
            total_max = max(total_max, fc["projected_cost"])
        y_max = total_max * 1.05 or 1.0
        for trace in _annotation_icon_traces(annotations_df, y_max):
            fig.add_trace(trace)
        return fig

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


def _build_kwh_figure(
    daily_df: pd.DataFrame,
    granularity: str = "daily",
    annotations_df: pd.DataFrame | None = None,
) -> go.Figure:
    if daily_df.empty:
        return _empty_figure("kWh")

    df = daily_df.sort_values("date").copy()
    df["date"] = pd.to_datetime(df["date"])

    if granularity == "monthly":
        date_series = df["date"].dt.tz_localize(None) if df["date"].dt.tz is not None else df["date"]
        df["month"] = date_series.dt.to_period("M").dt.to_timestamp()
        m_df = df.groupby("month", as_index=False).agg({"consumption_kwh": "sum"})

        fc = _compute_month_forecast(df)

        month_ms = 24 * 86400 * 1000
        offset_ms = 3 * 86400 * 1000
        fig = go.Figure()
        fig.add_bar(
            name="Consumption",
            x=m_df["month"],
            y=m_df["consumption_kwh"],
            offset=offset_ms,
            width=month_ms,
            marker=dict(
                color=theme.DATA_PRIMARY,
                cornerradius=2,
                line=dict(width=0),
            ),
            hovertemplate=(
                "<b>%{x|%B %Y}</b><br>"
                "Consumption: %{y:.2f} kWh<extra></extra>"
            ),
        )

        forecast_shapes = []
        if fc is not None:
            fig.add_bar(
                name="Forecast (Est.)",
                x=[fc["month_ts"]],
                y=[fc["forecast_kwh"]],
                offset=offset_ms,
                width=month_ms,
                marker=dict(
                    color="rgba(217, 93, 57, 0.08)",
                    line=dict(width=0),
                ),
                customdata=[[
                    fc["current_kwh"],
                    fc["forecast_kwh"],
                    fc["projected_kwh"],
                    fc["recorded_days"],
                    fc["remaining_days"],
                    fc["avg_daily_kwh"],
                ]],
                hovertemplate=(
                    "<b>%{x|%B %Y} (Month-End Forecast)</b><br>"
                    "Actual to Date (%{customdata[3]}d): %{customdata[0]:.2f} kWh<br>"
                    "Projected Rest of Month (%{customdata[4]}d): +%{customdata[1]:.2f} kWh<br>"
                    "<b>Est. Month Total: %{customdata[2]:.2f} kWh</b><br>"
                    "<span style='color:#7D7367'>Based on 30D avg: %{customdata[5]:.2f} kWh/day</span><extra></extra>"
                ),
            )
            x0 = fc["month_ts"] + pd.Timedelta(milliseconds=offset_ms)
            x1 = fc["month_ts"] + pd.Timedelta(milliseconds=offset_ms + month_ms)
            forecast_shapes.append(dict(
                type="rect",
                xref="x",
                yref="y",
                x0=x0,
                x1=x1,
                y0=fc["current_kwh"],
                y1=fc["projected_kwh"],
                line=dict(color=theme.DATA_PRIMARY, width=1.5, dash="dash"),
                fillcolor="rgba(217, 93, 57, 0.06)",
            ))

        fig.update_layout(**theme.base_layout(
            height=320,
            xaxis_title="", yaxis_title="kWh",
            barmode="stack",
            bargap=0.18,
            showlegend=False,
            shapes=_annotation_shapes(annotations_df) + forecast_shapes,
            hovermode="closest",
            dragmode="select",
            selectdirection="h",
            clickmode="event+select",
        ))
        fig.update_xaxes(**theme.xaxis_style(tickformat="%b %Y"))
        fig.update_yaxes(**theme.yaxis_style())
        total_max = float(m_df["consumption_kwh"].max() or 0)
        if fc is not None:
            total_max = max(total_max, fc["projected_kwh"])
        y_max = total_max * 1.05 or 1.0
        for trace in _annotation_icon_traces(annotations_df, y_max):
            fig.add_trace(trace)
        return fig

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


def legend_items(
    view: str = "cost",
    show_pins: bool = True,
    df: pd.DataFrame | None = None,
    granularity: str = "daily",
) -> list:
    items = []
    if view == "kwh":
        items.append(
            html.Span(
                [html.Span(className="legend-swatch", style={"background": theme.ORANGE}), "Consumption Energy"],
                className="legend-item",
            )
        )
        if granularity == "monthly":
            items.append(
                html.Span(
                    [
                        html.Span(
                            className="legend-swatch",
                            style={
                                "background": "rgba(217, 93, 57, 0.15)",
                                "border": f"1.5px dashed {theme.ORANGE}",
                            },
                        ),
                        "Forecast (Est.)",
                    ],
                    className="legend-item",
                    title="Month-end projection based on last 30-day daily average × remaining days",
                )
            )
    else:
        vat_label = "VAT (5%)"
        vat_title = "UK domestic electricity standard reduced rate: 5% VAT"
        if df is not None and not df.empty and "total_pence_vat" in df.columns:
            has_vat = (df["total_pence_vat"] > 0.001).any()
            has_zero_vat = (df["total_pence_vat"] <= 0.001).any()
            if has_zero_vat and not has_vat:
                vat_label = "VAT (0% Gov Zero-Rate)"
                vat_title = "Temporary 0% VAT applies across Great Britain from 1 Oct 2026 to 30 Jun 2027 (Gov.uk Domestic Electricity Relief)"
            elif has_zero_vat and has_vat:
                vat_label = "VAT (0% / 5%)"
                vat_title = "Selected window spans both 5% standard rate (< 1 Oct 2026) and 0% Gov temporary zero-rate period (>= 1 Oct 2026)"
            else:
                vat_label = "VAT (5%)"
                vat_title = "UK domestic electricity standard reduced rate: 5% VAT"

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
                    [html.Span(className="legend-swatch", style={"background": theme.PEACH}), vat_label],
                    className="legend-item",
                    title=vat_title,
                ),
            ]
        )
        if granularity == "monthly":
            items.append(
                html.Span(
                    [
                        html.Span(
                            className="legend-swatch",
                            style={
                                "background": "rgba(217, 93, 57, 0.15)",
                                "border": f"1.5px dashed {theme.ORANGE}",
                            },
                        ),
                        "Forecast (Est.)",
                    ],
                    className="legend-item",
                    title="Month-end projection based on last 30-day daily average × remaining days",
                )
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
    view_toggle = html.Div(
        dbc.RadioItems(
            id="daily-view-toggle",
            options=[
                {"label": "£", "value": "cost"},
                {"label": "kWh", "value": "kwh"},
            ],
            value="cost",
            class_name="segmented-group",
            input_class_name="btn-check",
            label_class_name="seg-btn",
            label_checked_class_name="active",
        ),
        className="setrum-toggle",
    )

    granularity_toggle = html.Div(
        dbc.RadioItems(
            id="daily-granularity-toggle",
            options=[
                {"label": "Daily", "value": "daily"},
                {"label": "Monthly", "value": "monthly"},
            ],
            value="daily",
            class_name="segmented-group",
            input_class_name="btn-check",
            label_class_name="seg-btn",
            label_checked_class_name="active",
        ),
        className="setrum-toggle",
    )

    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.H3("Cost & Consumption Over Time", id="daily-chart-title", className="mb-0"),
                            html.P("Track day-to-day bill drivers and weekend vs. weekday patterns — drag across any multi-day anomaly to total its cost and pin a note", className="text-muted small mb-0"),
                        ],
                        className="chart-title-wrap flex-grow-1",
                    ),
                    html.Div(
                        [
                            view_toggle,
                            granularity_toggle,
                            date_range_filter.render(
                                "daily",
                                presets=[
                                    ("7D", 7),
                                    ("14D", 14),
                                    ("30D", 30),
                                    ("90D", 90),
                                ],
                                default_days=30,
                            ),
                        ],
                        className="control-cluster",
                    ),
                ],
                className="chart-card-header daily-chart-card-header",
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
            html.Div(
                legend_items("cost"),
                id="daily-legend",
                className="chart-legend chart-legend--bottom-left",
            ),
        ],
        className="chart-card",
    )
