"""Shared Streamlit helpers: cached data, inputs from the sidebar, chart styling, formatting."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import data, engine

# Palette (validated categorical order + fixed status colours)
BLUE, ORANGE, AQUA, YELLOW, MAGENTA = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
SERIES = [BLUE, ORANGE, AQUA, YELLOW, MAGENTA]
GOOD, WARNING, SERIOUS, CRITICAL = "#0ca30c", "#fab219", "#ec835a", "#d03b3b"
INK, INK_2, MUTED, GRID = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1"
NEUTRAL = "#b7b6b0"

TIER_COLORS = {"Low": GOOD, "Watch": WARNING, "High": SERIOUS, "Critical": CRITICAL}
TIER_ICONS = {"Low": "🟢", "Watch": "🟡", "High": "🟠", "Critical": "🔴"}


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------

@st.cache_data
def load():
    p = data.parts()
    return p, data.inbound_schedule(p), data.suppliers()


def part_label(parts_df):
    return dict(zip(parts_df["part_id"], parts_df["part"]))


def inputs():
    """Read the sidebar controls (defined in app.py) from session state."""
    s = st.session_state
    shock = engine.Shock(part_ids=list(s.get("shock_parts", ["P102"])),
                         severity=s.get("severity", 50) / 100,
                         start_week=s.get("start_week", 3),
                         duration=s.get("duration", 4))
    mit = engine.Mitigation(spot_cover=s.get("spot_cover", 30) / 100,
                            spot_multiple=s.get("spot_multiple", 3.0),
                            freight_per_unit=s.get("freight", 12.0),
                            delay_weeks=s.get("delay", 1))
    a = engine.Assumptions(asp=s.get("asp", 47000.0),
                           gross_margin=s.get("gm", 18) / 100,
                           fixed_oh_per_vehicle=s.get("fixed_oh", 3200.0),
                           recovery=s.get("recovery", 60) / 100,
                           carrying_rate=s.get("carry", 25) / 100)
    return shock, mit, a


@st.cache_data(show_spinner=False)
def _run(shock_t, mit_t, a_t):
    p, ib, _ = load()
    return engine.run_scenario(p, ib, engine.Shock(list(shock_t[0]), *shock_t[1:]),
                               engine.Mitigation(*mit_t), engine.Assumptions(*a_t))


def run(shock, mit, a):
    return _run((tuple(shock.part_ids), shock.severity, shock.start_week, shock.duration),
                (mit.spot_cover, mit.spot_multiple, mit.freight_per_unit, mit.delay_weeks),
                (a.asp, a.gross_margin, a.fixed_oh_per_vehicle, a.recovery, a.carrying_rate))


# --------------------------------------------------------------------------
# Formatting
# --------------------------------------------------------------------------

def money(x, decimals=1):
    if abs(x) >= 1e9:
        return f"${x / 1e9:,.{decimals}f}B"
    if abs(x) >= 1e6:
        return f"${x / 1e6:,.{decimals}f}M"
    if abs(x) >= 1e3:
        return f"${x / 1e3:,.0f}K"
    return f"${x:,.0f}"


def num(x):
    return f"{x:,.0f}"


def header(title, subtitle):
    st.title(title)
    st.caption(subtitle)


def scenario_banner(shock, parts_df):
    names = part_label(parts_df)
    if not shock.part_ids or shock.severity == 0:
        st.info("No shortage is active. Pick a part and severity in the sidebar to stress the line.")
        return
    parts = ", ".join(names[p] for p in shock.part_ids)
    end = shock.start_week + shock.duration - 1
    st.markdown(
        f"**Active scenario:** {parts} inbound cut by **{shock.severity:.0%}** "
        f"in weeks **{shock.start_week} to {end}**.")


def sim_note():
    st.caption("All part, supplier and cost data is simulated for illustration. It is not Tesla data.")


# --------------------------------------------------------------------------
# Charts
# --------------------------------------------------------------------------

def style(fig, height=380, legend=True, ytitle=None, xtitle=None):
    fig.update_layout(
        height=height, margin=dict(l=70, r=20, t=40, b=60),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, sans-serif", size=13, color=INK_2),
        hoverlabel=dict(bgcolor="white", font_size=13, font_color=INK),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    font=dict(color=INK_2)),
        bargap=0.25,
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID, tickfont=dict(color=MUTED),
                     title=xtitle, zeroline=False, automargin=True)
    fig.update_yaxes(gridcolor=GRID, gridwidth=1, linecolor=GRID, tickfont=dict(color=MUTED),
                     title=ytitle, zeroline=False, automargin=True)
    return fig


def shade_weeks(fig, shock):
    if shock.part_ids and shock.severity > 0:
        fig.add_vrect(x0=shock.start_week - 0.5, x1=shock.start_week + shock.duration - 0.5,
                      fillcolor=CRITICAL, opacity=0.07, line_width=0,
                      annotation_text="Shortage window", annotation_position="top left",
                      annotation_font=dict(color=INK_2, size=12))
    return fig


def show(fig):
    st.plotly_chart(fig, width="stretch", theme=None,
                    config={"displayModeBar": False})
