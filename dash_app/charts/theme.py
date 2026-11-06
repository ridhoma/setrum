"""Shared Plotly theme for Setrum charts — Option 1: Editorial Field Notes.

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
PAPER         = "#FAF6F0"       # Archival Warm Paper
SURFACE       = "#FFFDF9"       # Card surface & masthead
SURFACE_ALT   = "#F3EDE2"       # Segmented controls, subtle fills
CORKBOARD     = "#EDE3D2"       # Dotted corkboard & rail
RULE          = "#E2D9C8"       # Hairline rule border
BORDER_STRONG = "#C8BCA8"       # Strong divider border

# Ink Hierarchy
INK_900       = "#181512"       # Espresso Ink
INK_700       = "#4A433B"
INK_500       = "#7D7367"
INK_300       = "#B5AA9C"
INK_200       = "#C8BCA8"
INK_100       = "#F3EDE2"

# Semantic Data & Signal Colors
ORANGE        = "#D95D39"       # Terracotta Vermilion — Consumption Hero
ORANGE_HOVER  = "#B84A29"
ORANGE_SOFT   = "#FADEC9"
COOL          = "#16697A"       # Deep Petrol Teal — Standing Charge
COOL_SOFT     = "#D5E5ED"
PEACH         = "#E89980"       # Warm Peach — VAT
ACCENT        = "#990F3D"       # Editorial Claret — Active tabs, primary action
ACCENT_HOVER  = "#7A0B30"
ACCENT_SOFT   = "#F4D9E1"
POSITIVE      = "#1E7E5A"
POSITIVE_SOFT = "#DCEEE6"
WARNING       = "#F4D35E"       # Warm Ochre Paper Tape
WARNING_SOFT  = "#F9EBC8"

# Sticky-note pastels (mirror of CSS --setrum-sticky-*)
CREAM         = "#F9EBC8"
PEACH_PASTEL  = "#FADEC9"
MINT          = "#D8E8DC"       # Sage
SKY           = "#D5E5ED"
LILAC         = "#E5DAE8"

# Typography
FONT_DISPLAY  = "'Fraunces', Georgia, 'Times New Roman', serif"
FONT_SANS     = "'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
FONT_MONO     = "'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace"

# Series roles. Terracotta = "data hero" rule lives here.
DATA_PRIMARY   = ORANGE       # consumption (kWh / cost)
DATA_SECONDARY = COOL         # standing charge — supporting cost
DATA_TERTIARY  = PEACH        # VAT — visually tied to consumption

# Annotation overlay default — warm ochre paper tape
ANNOTATION_DEFAULT_FILL = WARNING
ANNOTATION_FILL_OPACITY = 0.34

# Day-separator gridlines on time-axis charts (HH day boundaries, daily Monday markers)
DAY_SEPARATOR_COLOR = BORDER_STRONG


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
        gridcolor=RULE, gridwidth=1,
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
        opacity=0.8,
    )
