import plotly.graph_objects as go
import pandas as pd
import streamlit as st

from core import engine
from core.data import WEEKLY_PLAN
from core.ui import (load, inputs, run, money, num, header, scenario_banner, sim_note,
                     style, shade_weeks, show, BLUE, NEUTRAL, INK_2, CRITICAL)

parts_df, inbound, _ = load()
shock, mit, a = inputs()
r = run(shock, mit, a)
names = dict(zip(parts_df["part_id"], parts_df["part"]))

header("Executive Overview",
       "One quarter (13 weeks) of an EV assembly line, and what a part shortage does to output and cash.")
scenario_banner(shock, parts_df)

plan_total = WEEKLY_PLAN * len(r["weekly"])
built = r["weekly"]["built"].sum()
base_built = r["base_weekly"]["built"].sum()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Vehicles built", num(built), f"{built - base_built:,} vs baseline",
          help="Units actually built this quarter. Plan attainment = built / plan.")
c2.metric("Plan attainment", f"{built / plan_total:.1%}",
          f"{(built - base_built) / plan_total:.1%}",
          help="Built units as a share of the build plan.")
c3.metric("Revenue pushed out", money(r["revenue_deferred"]),
          help="Units not built this quarter x average selling price. Some is recovered next quarter.")
c4.metric("Total disruption cost", money(r["total_cost"]),
          help="Gross profit lost + under-absorbed overhead + purchase price variance (PPV) "
               "+ premium freight + carrying cost of stranded inventory.")
c5.metric("Inventory days (DIO)", f"{r['dio']:.1f}", f"{r['dio'] - r['base_dio']:+.1f} days",
          delta_color="inverse",
          help="Days inventory outstanding on the tracked BOM: average inventory value / daily COGS.")

st.markdown("#### Weekly build: plan vs baseline vs shortage scenario")
w = r["weekly"]
bw = r["base_weekly"]
fig = go.Figure()
fig.add_trace(go.Scatter(x=w.index, y=w["plan"], name="Build plan", mode="lines",
                         line=dict(color=INK_2, width=2, dash="dot"),
                         hovertemplate="Plan: %{y:,}<extra></extra>"))
fig.add_trace(go.Scatter(x=bw.index, y=bw["built"], name="Baseline (no shortage)", mode="lines+markers",
                         line=dict(color=NEUTRAL, width=2), marker=dict(size=8),
                         hovertemplate="Baseline: %{y:,}<extra></extra>"))
fig.add_trace(go.Scatter(x=w.index, y=w["built"], name="Scenario", mode="lines+markers",
                         line=dict(color=BLUE, width=2), marker=dict(size=8),
                         customdata=w["binding_part"].map(names).fillna("None"),
                         hovertemplate="Scenario: %{y:,}<br>Binding part: %{customdata}<extra></extra>"))
fig.update_layout(hovermode="x unified")
fig.update_yaxes(rangemode="tozero")
fig.update_xaxes(dtick=1)
show(shade_weeks(style(fig, ytitle="Vehicles", xtitle="Week"), shock))

left, right = st.columns([3, 2])

with left:
    st.markdown("#### Line-down watchlist")
    st.caption("Parts whose ending inventory drops below 3 days of production at any point in the quarter.")
    dos = engine.days_of_supply(r["inventory"], parts_df)
    sup = load()[2].set_index("supplier_id")["supplier"]
    rows = []
    for pid in dos.columns:
        m = dos[pid].min()
        if m < 3:
            status = ("🔴 Line down" if m < 0.5 else "🟠 Critical" if m < 1.5 else "🟡 Watch")
            p = parts_df.set_index("part_id").loc[pid]
            rows.append({"Status": status, "Part": names[pid], "Supplier": sup[p["supplier_id"]],
                         "Lowest days of supply": round(m, 1), "Week": int(dos[pid].idxmin()),
                         "Sole source": "Yes" if p["sole_source"] else "No"})
    if rows:
        st.dataframe(pd.DataFrame(rows).sort_values("Lowest days of supply"),
                     hide_index=True, width="stretch")
    else:
        st.success("No part drops below 3 days of supply this quarter.")

with right:
    st.markdown("#### Where the money goes")
    parts = {"Gross profit lost": r["gp_lost"], "Under-absorbed overhead": r["under_absorbed"],
             "Purchase price variance": r["ppv"], "Premium freight": r["freight"],
             "Stranded inventory carry": r["stranded_carry"]}
    df = pd.DataFrame({"item": list(parts), "value": list(parts.values())}).sort_values("value")
    fig = go.Figure(go.Bar(x=df["value"], y=df["item"], orientation="h", marker_color=BLUE,
                           text=[money(v) for v in df["value"]], textposition="outside",
                           cliponaxis=False, hovertemplate="%{y}: $%{x:,.0f}<extra></extra>"))
    style(fig, height=300, legend=False)
    fig.update_xaxes(showticklabels=False, showgrid=False)
    fig.update_yaxes(showgrid=False)
    fig.update_layout(margin=dict(r=60))
    show(fig)

if r["stranded_peak"] > 0:
    st.warning(
        f"**Stranded inventory:** while the line waits on the short part, other parts keep "
        f"arriving with nowhere to go. At the peak, **{money(r['stranded_peak'])}** of extra "
        f"inventory was sitting idle compared with the baseline. A cheap part can lock up a lot of cash.",
        icon="💡")

sim_note()
