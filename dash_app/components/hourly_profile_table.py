"""24-hour load profile comparison table (00:00..23:00).

Compares hourly kWh across two user-configurable presets:
  - Preset 1 (defaults to Last 7D)
  - Preset 2 (defaults to Last 30D)
  - Delta (Preset 1 − Preset 2)

Each preset header is a dropdown trigger that opens a selection modal:
Left: Quick presets (Last 7D, Last 14D, Last 30D, Last 90D, Custom)
Right: Calendar showing the selected period with interactive date selection.
"""

from __future__ import annotations

import calendar
import datetime

import dash_bootstrap_components as dbc
from dash import dcc, html


def resolve_preset_dates(preset: str, max_date_str: str) -> tuple[str, str]:
    """Return (start_date, end_date) for a preset code relative to max_date."""
    try:
        max_d = datetime.date.fromisoformat(max_date_str)
    except (ValueError, TypeError):
        max_d = datetime.date.today()

    if preset == "7D":
        return (max_d - datetime.timedelta(days=6)).isoformat(), max_d.isoformat()
    elif preset == "14D":
        return (max_d - datetime.timedelta(days=13)).isoformat(), max_d.isoformat()
    elif preset == "30D":
        return (max_d - datetime.timedelta(days=29)).isoformat(), max_d.isoformat()
    elif preset == "90D":
        return (max_d - datetime.timedelta(days=89)).isoformat(), max_d.isoformat()
    return max_d.isoformat(), max_d.isoformat()


def format_preset_label(preset: str | None, start_date: str | None, end_date: str | None) -> str:
    """Return concise user-facing label for preset button."""
    if preset in ("7D", "14D", "30D", "90D"):
        return f"Last {preset}"
    if not start_date or not end_date:
        return "Select period"
    if start_date == end_date:
        return start_date
    try:
        s_dt = datetime.date.fromisoformat(start_date)
        e_dt = datetime.date.fromisoformat(end_date)
        if s_dt.year == e_dt.year:
            return f"{s_dt.strftime('%b %d')} – {e_dt.strftime('%b %d')}"
        return f"{s_dt.strftime('%b %d, %Y')} – {e_dt.strftime('%b %d, %Y')}"
    except (ValueError, TypeError):
        return f"{start_date} – {end_date}"


def _fmt_kwh(val: float | None, decimals: int = 3) -> str:
    if val is None:
        return "—"
    return f"{val:.{decimals}f}"


def _bar_cell(
    val: float | None,
    x_max: float,
    is_primary: bool = False,
    is_peak: bool = False,
) -> html.Td:
    """Render a table cell with an inline horizontal bar scaled to [0, x_max]."""
    pct = 0.0
    if val is not None and x_max > 0:
        pct = min(100.0, max(0.0, (float(val) / x_max) * 100.0))

    bar_cls = "hourly-bar-fill " + (
        "hourly-bar-fill--primary" if is_primary else "hourly-bar-fill--avg"
    )
    td_cls = "hourly-col-val"
    if is_primary:
        td_cls += " hourly-col-latest"
    if is_peak:
        td_cls += " hourly-col-peak"

    return html.Td(
        html.Div(
            [
                html.Div(
                    className=bar_cls,
                    style={"width": f"{pct:.1f}%"},
                ),
                html.Span(_fmt_kwh(val), className="hourly-cell-text"),
            ],
            className="hourly-cell-track",
        ),
        className=td_cls,
    )


def _delta_cell(val: float | None, max_abs_delta: float) -> html.Td:
    """Render a Delta cell with signed kWh text and directional color/bar fill."""
    if val is None:
        return html.Td(
            html.Div(
                html.Span("—", className="hourly-cell-text text-muted"),
                className="hourly-cell-track",
            ),
            className="hourly-col-val hourly-col-delta",
        )

    pct = 0.0
    if max_abs_delta > 0:
        pct = min(100.0, max(0.0, (abs(val) / max_abs_delta) * 100.0))

    if val > 0.0001:
        text = f"+{val:.3f}"
        text_cls = "hourly-cell-text hourly-text--delta-pos"
        bar_cls = "hourly-bar-fill hourly-bar-fill--delta-pos"
    elif val < -0.0001:
        text = f"{val:.3f}"
        text_cls = "hourly-cell-text hourly-text--delta-neg"
        bar_cls = "hourly-bar-fill hourly-bar-fill--delta-neg"
    else:
        text = "0.000"
        text_cls = "hourly-cell-text text-muted"
        bar_cls = "hourly-bar-fill"

    return html.Td(
        html.Div(
            [
                html.Div(
                    className=bar_cls,
                    style={"width": f"{pct:.1f}%"},
                ),
                html.Span(text, className=text_cls),
            ],
            className="hourly-cell-track",
        ),
        className="hourly-col-val hourly-col-delta",
    )


def render_rows_and_footer(profile: dict) -> tuple[list, list]:
    """Render rows and footer for Preset 1, Preset 2, and Delta (1 - 2)."""
    rows = profile.get("rows") or []

    # Shared scale for Preset 1 and Preset 2 bars
    all_p_vals = [
        float(v)
        for r in rows
        for v in (r.get("p1_kwh"), r.get("p2_kwh"))
        if v is not None
    ]
    x_max = max(all_p_vals) if all_p_vals else 1.0

    # Scale for Delta bars
    all_deltas = [
        abs(float(r["delta_kwh"]))
        for r in rows
        if r.get("delta_kwh") is not None
    ]
    max_abs_delta = max(all_deltas) if all_deltas else 1.0

    sum_p1 = sum(r["p1_kwh"] for r in rows if r.get("p1_kwh") is not None)
    sum_p2 = sum(r["p2_kwh"] for r in rows if r.get("p2_kwh") is not None)
    has_p1 = any(r.get("p1_kwh") is not None for r in rows)
    has_p2 = any(r.get("p2_kwh") is not None for r in rows)

    tbody_rows = []
    for r in rows:
        p1 = r.get("p1_kwh")
        p2 = r.get("p2_kwh")
        delta = r.get("delta_kwh")
        is_peak = p1 is not None and x_max > 0 and p1 >= x_max * 0.75
        tbody_rows.append(
            html.Tr(
                [
                    html.Td(r["hour"], className="hourly-col-hour"),
                    _bar_cell(p1, x_max, is_primary=True, is_peak=is_peak),
                    _bar_cell(p2, x_max, is_primary=False, is_peak=False),
                    _delta_cell(delta, max_abs_delta),
                ]
            )
        )

    if has_p1 and has_p2:
        sum_delta = sum_p1 - sum_p2
        if sum_delta > 0.001:
            delta_footer = html.Span(f"+{sum_delta:.2f} kWh", className="delta-badge delta-up")
        elif sum_delta < -0.001:
            delta_footer = html.Span(f"{sum_delta:.2f} kWh", className="delta-badge delta-down")
        else:
            delta_footer = html.Span("0.00 kWh", className="delta-badge")
    else:
        delta_footer = html.Span("—", className="text-muted")

    tfoot_rows = [
        html.Tr(
            [
                html.Td("Total (24h)", className="hourly-col-hour"),
                html.Td(
                    f"{sum_p1:.2f} kWh" if has_p1 else "—",
                    className="hourly-col-val hourly-col-latest",
                ),
                html.Td(
                    f"{sum_p2:.2f} kWh" if has_p2 else "—",
                    className="hourly-col-val",
                ),
                html.Td(
                    delta_footer,
                    className="hourly-col-val hourly-col-delta",
                ),
            ]
        )
    ]
    return tbody_rows, tfoot_rows


def render_calendar_grid(
    year: int,
    month: int,
    start_date: str | None,
    end_date: str | None,
    min_date: str | None = None,
    max_date: str | None = None,
) -> html.Table:
    """Render a month calendar grid with day buttons and range highlights."""
    cal = calendar.Calendar(firstweekday=0)  # Monday first
    weeks = cal.monthdatescalendar(year, month)

    thead = html.Thead(
        html.Tr([html.Th(day, className="cal-th") for day in ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]])
    )

    tbody_trs = []
    for week in weeks:
        tds = []
        for d in week:
            d_iso = d.isoformat()
            is_outside = (d.month != month)
            is_disabled = False
            if min_date and d_iso < min_date:
                is_disabled = True
            if max_date and d_iso > max_date:
                is_disabled = True

            in_range = False
            is_start = False
            is_end = False
            if start_date and end_date:
                s, e = min(start_date, end_date), max(start_date, end_date)
                in_range = (s <= d_iso <= e)
                is_start = (d_iso == s)
                is_end = (d_iso == e)
            elif start_date:
                is_start = (d_iso == start_date)
                in_range = is_start

            cls_parts = ["cal-day"]
            if is_outside:
                cls_parts.append("cal-day--outside")
            if is_disabled:
                cls_parts.append("cal-day--disabled")
            if in_range:
                cls_parts.append("cal-day--in-range")
            if is_start:
                cls_parts.append("cal-day--start")
            if is_end:
                cls_parts.append("cal-day--end")

            btn = html.Button(
                str(d.day),
                id={"type": "hourly-cal-day", "date": d_iso},
                className=" ".join(cls_parts),
                disabled=is_disabled,
                type="button",
            )
            tds.append(html.Td(btn, className="cal-td"))
        tbody_trs.append(html.Tr(tds))

    return html.Table([thead, html.Tbody(tbody_trs)], className="hourly-cal-table")


def render_preset_modal() -> dbc.Modal:
    """Render the dropdown modal for preset & calendar period selection."""
    return dbc.Modal(
        [
            dbc.ModalHeader(
                dbc.ModalTitle("Select Preset Period", id="hourly-modal-title"),
                close_button=True,
                className="modal-header",
            ),
            dbc.ModalBody(
                html.Div(
                    [
                        # Left: Presets Sidebar
                        html.Div(
                            [
                                html.Div("Presets", className="hourly-sidebar-heading"),
                                html.Div(
                                    [
                                        html.Button("Last 7D", id="hourly-opt-7D", className="hourly-preset-opt", type="button"),
                                        html.Button("Last 14D", id="hourly-opt-14D", className="hourly-preset-opt", type="button"),
                                        html.Button("Last 30D", id="hourly-opt-30D", className="hourly-preset-opt", type="button"),
                                        html.Button("Last 90D", id="hourly-opt-90D", className="hourly-preset-opt", type="button"),
                                        html.Button("Custom", id="hourly-opt-custom", className="hourly-preset-opt", type="button"),
                                    ],
                                    className="hourly-preset-opt-list",
                                ),
                            ],
                            className="hourly-modal-sidebar",
                        ),
                        # Right: Calendar Pane
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.Button("◀", id="hourly-cal-prev-btn", className="hourly-cal-nav-btn", type="button"),
                                        html.Div(id="hourly-cal-month-heading", className="hourly-cal-month-heading"),
                                        html.Button("▶", id="hourly-cal-next-btn", className="hourly-cal-nav-btn", type="button"),
                                    ],
                                    className="hourly-cal-nav",
                                ),
                                html.Div(id="hourly-cal-grid", className="hourly-cal-grid"),
                                html.Div(
                                    [
                                        html.Div(id="hourly-cal-summary", className="hourly-cal-summary"),
                                        html.Div(
                                            [
                                                html.Span("From:", className="hourly-input-label"),
                                                dcc.Input(
                                                    id="hourly-cal-input-start",
                                                    type="text",
                                                    placeholder="YYYY-MM-DD",
                                                    className="hourly-date-input",
                                                    debounce=True,
                                                ),
                                                html.Span("To:", className="hourly-input-label ms-2"),
                                                dcc.Input(
                                                    id="hourly-cal-input-end",
                                                    type="text",
                                                    placeholder="YYYY-MM-DD",
                                                    className="hourly-date-input",
                                                    debounce=True,
                                                ),
                                            ],
                                            className="hourly-cal-inputs-wrap",
                                        ),
                                    ],
                                    className="hourly-cal-bottom-bar",
                                ),
                            ],
                            className="hourly-modal-cal-pane",
                        ),
                    ],
                    className="hourly-modal-layout",
                ),
                className="p-0",
            ),
            dbc.ModalFooter(
                [
                    dbc.Button("Cancel", id="hourly-modal-cancel-btn", className="btn-secondary-editorial me-2", size="sm"),
                    dbc.Button("Apply Period", id="hourly-modal-apply-btn", className="btn-primary-editorial", size="sm"),
                ],
                className="modal-footer",
            ),
        ],
        id="hourly-preset-modal",
        is_open=False,
        centered=True,
        size="lg",
        className="hourly-preset-modal",
    )


def render() -> html.Div:
    preset_1_header = html.Div(
        [
            html.Div("Preset 1", className="hourly-th-badge"),
            html.Button(
                [
                    html.Span("Last 7D", id="hourly-preset-1-label"),
                    html.Span(" ▾", className="hourly-th-arrow"),
                ],
                id="hourly-preset-1-btn",
                className="hourly-preset-trigger-btn",
                type="button",
                title="Click to configure Preset 1 period",
            ),
        ],
        className="hourly-th-btn-wrap",
    )

    preset_2_header = html.Div(
        [
            html.Div("Preset 2", className="hourly-th-badge"),
            html.Button(
                [
                    html.Span("Last 30D", id="hourly-preset-2-label"),
                    html.Span(" ▾", className="hourly-th-arrow"),
                ],
                id="hourly-preset-2-btn",
                className="hourly-preset-trigger-btn",
                type="button",
                title="Click to configure Preset 2 period",
            ),
        ],
        className="hourly-th-btn-wrap",
    )

    delta_header = html.Div(
        [
            html.Div("Delta (1 - 2)", className="hourly-th-title"),
            html.Div("P1 − P2", className="hourly-th-sub"),
        ],
        className="hourly-th-delta-wrap",
    )

    table = html.Table(
        [
            html.Thead(
                html.Tr(
                    [
                        html.Th("Hour", className="hourly-col-hour"),
                        html.Th(
                            preset_1_header,
                            className="hourly-col-val hourly-th-preset",
                        ),
                        html.Th(
                            preset_2_header,
                            className="hourly-col-val hourly-th-preset",
                        ),
                        html.Th(
                            delta_header,
                            className="hourly-col-val hourly-th-delta",
                        ),
                    ]
                )
            ),
            html.Tbody(id="hourly-profile-tbody"),
            html.Tfoot(id="hourly-profile-tfoot"),
        ],
        className="hourly-profile-table",
    )

    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.H3("24-Hour Load Profile (kWh)", className="mb-0"),
                            html.P(
                                "Compare any two timeframes across 24 hours to analyze baseload shifts, daily habits, and peak timing",
                                className="text-muted small mb-0",
                            ),
                        ],
                        className="chart-title-wrap w-100",
                    ),
                ],
                className="chart-card-header",
            ),
            html.Div(table, className="hourly-table-scroll"),
            render_preset_modal(),
        ],
        className="chart-card hourly-card-wrap h-100 mb-0",
    )
