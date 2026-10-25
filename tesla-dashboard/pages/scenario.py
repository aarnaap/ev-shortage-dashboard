from dataclasses import replace

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import engine
from core.ui import (load, inputs, run, money, num, header, scenario_banner, sim_note,
                     style, shade_weeks, show, BLUE, ORANGE, AQUA, GOOD, CRITICAL, INK_2, GRID)

parts_df, inbound, _ = load()
shock, mit, a = inputs()
r = run(shock, mit, a)

header("Shortage P&L Impact",
       "Turning missing parts into the numbers a finance team reports: margin, variance, and cash.")
scenario_banner(shock, parts_df)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Units short vs baseline", num(r["units_short"]),
          help="Vehicles the baseline would have built that the scenario could not.")
c2.metric("Gross profit lost", money(r["gp_lost"]),
          help=f"Permanently lost units ({1 - a.recovery:.0%} of units short) x ASP x gross margin.")
c3.metric("Under-absorbed overhead", money(r["under_absorbed"]),
          help="Fixed plant costs still incurred while the line sits idle. They hit COGS "
               "without cars to spread them across.")
c4.metric("Purchase price variance", money(r["ppv"]),
          help="PPV = (actual price - standard cost) x quantity. Here it is the broker premium "
               "on spot buys.")
c5.metric("Premium freight", money(r["freight"]),
          help="Air freight to expedite spot-bought parts.")

left, right = st.columns([3, 2])
with left:
    st.markdown("#### Cost of the disruption")
    items = [("Gross profit lost", r["gp_lost"]), ("Under-absorbed overhead", r["under_absorbed"]),
             ("Purchase price variance", r["ppv"]), ("Premium freight", r["freight"]),
             ("Stranded inventory carry", r["stranded_carry"])]
    fig = go.Figure(go.Waterfall(
        x=[i[0] for i in items] + ["Total"],
        y=[i[1] for i in items] + [0],
        measure=["relative"] * len(items) + ["total"],
        text=[money(i[1]) for i in items] + [money(r["total_cost"])],
        textposition="outside", cliponaxis=False,
        connector=dict(line=dict(color=GRID, width=1)),
        increasing=dict(marker=dict(color=ORANGE)),
        totals=dict(marker=dict(color=BLUE)),
        hovertemplate="%{x}: $%{y:,.0f}<extra></extra>"))
    style(fig, height=400, legend=False)
    fig.update_yaxes(tickprefix="$", tickformat="~s")
    show(fig)

with right:
    st.markdown("#### Stranded inventory")
    st.caption("Extra inventory value sitting idle vs baseline, because the line cannot consume it.")
    base_val = engine.inventory_value(r["base_inventory"], parts_df)
    scen_val = engine.inventory_value(r["inventory"], parts_df)
    diff = (scen_val - base_val).clip(lower=0)
    fig = go.Figure(go.Bar(x=diff.index, y=diff.values, marker_color=BLUE,
                           hovertemplate="Week %{x}: $%{y:,.0f}<extra></extra>"))
    style(fig, height=400, legend=False, xtitle="Week")
    fig.update_yaxes(tickprefix="$", tickformat="~s")
    fig.update_xaxes(dtick=1)
    show(shade_weeks(fig, shock))

st.divider()
st.markdown("### Should we pay up for spot buys?")
st.caption("Each point reruns the full simulation at a different spot buy cover, holding everything else "
           "constant. Spending on PPV and freight is worth it only while it saves more margin than it costs.")


@st.cache_data(show_spinner="Running mitigation scenarios...")
def mitigation_curve(shock_t, mit_t, a_t):
    p, ib, _ = load()
    sh = engine.Shock(list(shock_t[0]), *shock_t[1:])
    base_mit = engine.Mitigation(*mit_t)
    a_ = engine.Assumptions(*a_t)
    rows = []
    for cover in np.arange(0, 1.01, 0.1):
        res = engine.run_scenario(p, ib, sh, replace(base_mit, spot_cover=cover), a_)
        rows.append({"cover": cover,
                     "expedite_spend": res["ppv"] + res["freight"],
                     "shortage_cost": res["gp_lost"] + res["under_absorbed"] + res["stranded_carry"],
                     "total": res["total_cost"]})
    return pd.DataFrame(rows)


curve = mitigation_curve(
    (tuple(shock.part_ids), shock.severity, shock.start_week, shock.duration),
    (mit.spot_cover, mit.spot_multiple, mit.freight_per_unit, mit.delay_weeks),
    (a.asp, a.gross_margin, a.fixed_oh_per_vehicle, a.recovery, a.carrying_rate))

best = curve.loc[curve["total"].idxmin()]
none = curve.iloc[0]
fig = go.Figure()
for col, name, color in [("shortage_cost", "Cost of the shortage", ORANGE),
                         ("expedite_spend", "Spend on spot buys (PPV + freight)", AQUA),
                         ("total", "Total", BLUE)]:
    fig.add_trace(go.Scatter(x=curve["cover"], y=curve[col], name=name, mode="lines+markers",
                             line=dict(color=color, width=2 if col != "total" else 3),
                             marker=dict(size=8),
                             hovertemplate=f"{name}: $%{{y:,.0f}}<extra></extra>"))
fig.add_trace(go.Scatter(x=[best["cover"]], y=[best["total"]], mode="markers", name="Lowest total cost",
                         marker=dict(size=16, color=BLUE, symbol="star", line=dict(color="white", width=2)),
                         hovertemplate="Best: %{x:.0%} cover<extra></extra>"))
fig.add_vline(x=mit.spot_cover, line=dict(color=INK_2, dash="dot", width=1.5),
              annotation_text="Your setting", annotation_font=dict(color=INK_2))
fig.update_layout(hovermode="x unified")
style(fig, height=400, xtitle="Share of shortfall covered by spot buys")
fig.update_xaxes(tickformat=".0%")
fig.update_yaxes(tickprefix="$", tickformat="~s", rangemode="tozero")
show(fig)

saved = none["total"] - best["total"]
if best["cover"] == 0:
    st.info(f"**Recommendation: do not expedite.** At a {mit.spot_multiple:.1f}x spot price, buying "
            f"from brokers costs more than the margin it protects for this part.", icon="🧮")
else:
    roi = (none["shortage_cost"] - best["shortage_cost"]) / max(best["expedite_spend"], 1)
    st.success(f"**Recommendation: cover about {best['cover']:.0%} of the shortfall on the spot market.** "
               f"That cuts total disruption cost by **{money(saved)}** versus doing nothing. Every $1 "
               f"spent on spot buys and freight protects about **${roi:,.2f}** of margin and overhead.",
               icon="🧮")

st.divider()
st.markdown("### Sensitivity: how bad can it get?")
st.caption("Total disruption cost for the selected part(s) across every combination of severity and "
           "duration, starting in the selected week, with your mitigation settings.")


@st.cache_data(show_spinner="Running sensitivity grid...")
def sensitivity(shock_t, mit_t, a_t):
    p, ib, _ = load()
    sevs = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    durs = list(range(1, 9))
    z = np.zeros((len(sevs), len(durs)))
    for i, s in enumerate(sevs):
        for j, d in enumerate(durs):
            sh = engine.Shock(list(shock_t[0]), s, shock_t[2], d)
            z[i, j] = engine.run_scenario(p, ib, sh, engine.Mitigation(*mit_t),
                                          engine.Assumptions(*a_t))["total_cost"]
    return sevs, durs, z


if shock.part_ids:
    sevs, durs, z = sensitivity(
        (tuple(shock.part_ids), shock.severity, shock.start_week, shock.duration),
        (mit.spot_cover, mit.spot_multiple, mit.freight_per_unit, mit.delay_weeks),
        (a.asp, a.gross_margin, a.fixed_oh_per_vehicle, a.recovery, a.carrying_rate))
    fig = go.Figure(go.Heatmap(
        z=z, x=[f"{d} wk" for d in durs], y=[f"{s:.0%}" for s in sevs],
        colorscale=[[0, "#cde2fb"], [0.5, "#3987e5"], [1, "#0d366b"]], xgap=2, ygap=2,
        text=[[money(v, 0) for v in row] for row in z], texttemplate="%{text}",
        textfont=dict(size=11),
        hovertemplate="Severity %{y}, duration %{x}<br>Total cost: %{text}<extra></extra>",
        colorbar=dict(title="Cost", thickness=12, tickprefix="$", tickformat="~s")))
    style(fig, height=440, legend=False, xtitle="Shortage duration", ytitle="Inbound lost")
    fig.update_yaxes(showgrid=False)
    show(fig)
else:
    st.info("Pick a part in the sidebar to see the sensitivity grid.")

sim_note()
