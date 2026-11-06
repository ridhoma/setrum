"""24-hour load profile comparison table (00:00..23:00).

Compares hourly kWh on a user-selectable date (via a single-date calendar
picker in the 2nd column header, defaulting to the latest available date)
against the rolling 7-day and 30-day hourly averages.
All 3 value columns share a single unified scale: [x_min=0, x_max=max(all 3 columns)].
"""

from __future__ import annotations

from dash import dcc, html


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


def render_rows_and_footer(profile: dict) -> tuple[list, list]:
    rows = profile.get("rows") or []

    # Unified scale across all 3 columns: x_min = 0, x_max = max of all 3 columns
    all_vals = [
        float(v)
        for r in rows
        for v in (r.get("latest_kwh"), r.get("avg_7d_kwh"), r.get("avg_30d_kwh"))
        if v is not None
    ]
    x_max = max(all_vals) if all_vals else 1.0

    sum_latest = sum(r["latest_kwh"] for r in rows if r.get("latest_kwh") is not None)
    sum_7d = sum(r["avg_7d_kwh"] for r in rows if r.get("avg_7d_kwh") is not None)
    sum_30d = sum(r["avg_30d_kwh"] for r in rows if r.get("avg_30d_kwh") is not None)
    has_latest = any(r.get("latest_kwh") is not None for r in rows)
    has_any = bool(all_vals)

    tbody_rows = []
    for r in rows:
        lv = r.get("latest_kwh")
        v7 = r.get("avg_7d_kwh")
        v30 = r.get("avg_30d_kwh")
        is_peak = lv is not None and x_max > 0 and lv >= x_max * 0.75
        tbody_rows.append(
            html.Tr(
                [
                    html.Td(r["hour"], className="hourly-col-hour"),
                    _bar_cell(lv, x_max, is_primary=True, is_peak=is_peak),
                    _bar_cell(v7, x_max, is_primary=False, is_peak=False),
                    _bar_cell(v30, x_max, is_primary=False, is_peak=False),
                ]
            )
        )

    tfoot_rows = [
        html.Tr(
            [
                html.Td("Total (24h)", className="hourly-col-hour"),
                html.Td(
                    f"{sum_latest:.2f} kWh" if has_latest else "—",
                    className="hourly-col-val hourly-col-latest",
                ),
                html.Td(
                    f"{sum_7d:.2f} kWh" if has_any else "—",
                    className="hourly-col-val",
                ),
                html.Td(
                    f"{sum_30d:.2f} kWh" if has_any else "—",
                    className="hourly-col-val",
                ),
            ]
        )
    ]
    return tbody_rows, tfoot_rows


def render() -> html.Div:
    date_picker_header = html.Div(
        [
            dcc.DatePickerSingle(
                id="hourly-profile-date-picker",
                display_format="YYYY-MM-DD",
                placeholder="Select date",
                className="hourly-header-datepicker",
                persistence=True,
                persistence_type="session",
            ),
        ],
        className="hourly-dp-pill",
        title="Click to pick any date to compare against 7d and 30d averages",
    )

    table = html.Table(
        [
            html.Thead(
                html.Tr(
                    [
                        html.Th("Hour", className="hourly-col-hour"),
                        html.Th(
                            date_picker_header,
                            className="hourly-col-val hourly-th-datepicker",
                        ),
                        html.Th("AVG(Prev. 7 Days)", className="hourly-col-val"),
                        html.Th("AVG(Prev. 30 Days)", className="hourly-col-val"),
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
                                "Compare any day's hourly rhythm against its prior 7- and 30-day baselines to spot creeping overnight baseload and unusual daytime spikes",
                                className="text-muted small mb-0",
                            ),
                        ],
                        className="chart-title-wrap w-100",
                    ),
                ],
                className="chart-card-header",
            ),
            html.Div(table, className="hourly-table-scroll"),
        ],
        className="chart-card hourly-card-wrap h-100 mb-0",
    )
