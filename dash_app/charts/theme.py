"""Shared Plotly theme for Setrum charts.

Plotly can't read CSS custom properties, so the design tokens are mirrored
here as Python constants. If you change a value in setrum.css `:root`,
change it here too — they're the same source-of-truth, deliberately
duplicated across the language boundary.

Usage:
    from dash_app.charts import theme
    fig.update_layout(**theme.base_layout())
    fig.update_xaxes(**theme.xaxis_style(tickformat="%b %d"))
    fig.update_yaxes(**theme.yaxis_style(tickprefix="£"))
"""

from __future__ import annotations

# ── Token mirrors (keep in sync with assets/setrum.css :root) ──────────────
PAPER         = "#FCFAF6"
SURFACE       = "#FFFFFF"
INK_900       = "#1A1714"
INK_700       = "#4A433D"
INK_500       = "#847A6F"
INK_300       = "#C9C0B5"
INK_200       = "#DCD4C8"
INK_100       = "#EFE9DE"
RULE          = "#E8DFD0"

ORANGE        = "#CC785C"
ORANGE_SOFT   = "#F1D9CA"
ACCENT        = "#990F3D"
COOL          = "#0D7680"
COOL_SOFT     = "#D2E5E7"
POSITIVE      = "#1A8A6E"
WARNING       = "#B68D00"
WARNING_SOFT  = "#F2E6BF"

# Sticky-note pastels (mirror of CSS --setrum-sticky-*). Reusable in
# charts that want a pastel wash without inventing new tokens.
PEACH         = "#FBE4D2"
MINT          = "#D8EAD8"
SKY           = "#D4E4EC"
LILAC         = "#E2D8E8"
CREAM         = "#F7E8C7"

FONT_SANS = "Inter, -apple-system, BlinkMacSystemFont, sans-serif"
FONT_MONO = "JetBrains Mono, SF Mono, Menlo, monospace"

# Series roles. The orange = "data hero" rule lives here.
DATA_PRIMARY   = ORANGE       # consumption (kWh / cost)
DATA_SECONDARY = COOL         # standing charge — supporting cost
DATA_TERTIARY  = ORANGE_SOFT  # VAT — visually tied to consumption (math says so)

# Annotation overlay default — soft warm gold so it reads as paper-tape on
# the chart without competing with the data colors.
ANNOTATION_DEFAULT_FILL = WARNING_SOFT
ANNOTATION_FILL_OPACITY = 0.45  # WARNING_SOFT is already pale; bump opacity

# Day-separator gridlines on time-axis charts (HH day boundaries, daily
# Monday markers). Lighter than the y-grid so they read as secondary.
DAY_SEPARATOR_COLOR = INK_200


def base_layout(**extra) -> dict:
    base = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT_SANS, size=12, color=INK_700),
        margin=dict(l=56, r=16, t=24, b=40),
        hoverlabel=dict(
            bgcolor=SURFACE,
            bordercolor=RULE,
            font=dict(family=FONT_MONO, size=12, color=INK_900),
        ),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            font=dict(family=FONT_SANS, size=11, color=INK_700),
            bgcolor="rgba(0,0,0,0)",
        ),
    )
    base.update(extra)
    return base


def xaxis_style(**extra) -> dict:
    base = dict(
        showgrid=False,
        showline=True, linecolor=RULE, linewidth=1,
        ticks="outside", tickcolor=INK_300, ticklen=4,
        tickfont=dict(family=FONT_MONO, size=10, color=INK_500),
    )
    base.update(extra)
    return base


def yaxis_style(**extra) -> dict:
    base = dict(
        gridcolor=INK_100, gridwidth=1,
        zeroline=False, showline=False, ticks="",
        tickfont=dict(family=FONT_MONO, size=10, color=INK_500),
    )
    base.update(extra)
    return base


def with_alpha(hex_color: str, alpha: float) -> str:
    """Return ``rgba(R,G,B,alpha)`` for a ``#RRGGBB`` token.

    Plotly's ``fillcolor`` has no separate opacity prop — alpha has to live
    inside the colour string. Use this when you want a fill to let the
    underlying gridlines show through.
    """
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def day_separator_shape(x) -> dict:
    """Vertical hairline at x — used for HH day boundaries / daily Mondays."""
    return dict(
        type="line",
        x0=x, x1=x, xref="x",
        y0=0, y1=1, yref="paper",
        line=dict(color=DAY_SEPARATOR_COLOR, dash="dot", width=1),
        opacity=1.0,
    )
