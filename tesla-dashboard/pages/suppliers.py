import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import engine
from core.ui import (load, money, header, sim_note, style, show,
                     SERIES, TIER_COLORS, TIER_ICONS, INK_2, GRID)

parts_df, _, _ = load()
risk = engine.supplier_risk(parts_df)

header("Supplier Risk",
       "Which suppliers could stop the line, and how much spend sits with them?")

high = risk["risk_tier"].isin(["High", "Critical"])
tier1_spend = risk.loc[risk["tier"] == 1, "annual_spend"].sum()
high_spend = risk.loc[high & (risk["tier"] == 1), "annual_spend"].sum()
tier2 = risk[risk["tier"] == 2].iloc[0]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Critical suppliers", int((risk["risk_tier"] == "Critical").sum()))
c2.metric("Tier 1 spend at High/Critical risk", f"{high_spend / tier1_spend:.0%}",
          help="Share of annual tier 1 spend with suppliers scored High or Critical.")
c3.metric("Sole-source parts", f"{int(parts_df['sole_source'].sum())} of {len(parts_df)}",
          help="Parts with only one qualified supplier. No backup if that supplier slips.")
c4.metric("PCBAs on one tier 2 fab", int(tier2["parts_supplied"]),
          help="Hidden concentration: several different tier 1 boards depend on the same chip fab.")

n_t1 = parts_df.loc[parts_df["tier2_source"] == tier2["supplier_id"], "supplier_id"].nunique()
st.warning(
    f"**Hidden tier 2 risk:** {int(tier2['parts_supplied'])} different circuit boards from {n_t1} "
    f"different tier 1 suppliers all rely on chips from **{tier2['supplier']}** "
    f"(average lead time {tier2['lt_mean_days']} days). On paper the boards look diversified. "
    f"Underneath, one fab outage hits all of them at once. This is the pattern that turned the "
    f"2021 chip shortage into an industry-wide line-down event.", icon="⚠️")

left, right = st.columns(2)

with left:
    st.markdown("#### Reliability map")
    st.caption("Bottom right is the danger zone: unpredictable lead times and poor on-time delivery. "
               "Bubble size is annual spend.")
    fig = go.Figure()
    for tier in ["Critical", "High", "Watch", "Low"]:
        d = risk[risk["risk_tier"] == tier]
        if d.empty:
            continue
        fig.add_trace(go.Scatter(
            x=d["lt_cv"], y=d["otif"], mode="markers+text", name=f"{TIER_ICONS[tier]} {tier}",
            text=d["supplier"].str.split().str[0] if tier in ("Critical", "High") else None,
            textposition="top center", textfont=dict(size=11, color=INK_2),
            marker=dict(size=(d["annual_spend"] / risk["annual_spend"].max()) ** 0.5 * 42 + 10,
                        color=TIER_COLORS[tier], opacity=0.85, line=dict(color="white", width=2)),
            customdata=d[["supplier", "annual_spend", "risk_score"]],
            hovertemplate="<b>%{customdata[0]}</b><br>OTIF %{y:.0%}<br>Lead time CV %{x:.2f}"
                          "<br>Spend $%{customdata[1]:,.0f}<br>Risk %{customdata[2]:.0f}<extra></extra>"))
    style(fig, height=430, xtitle="Lead time variability (std dev / mean)", ytitle="On-time in-full (OTIF)")
    fig.update_yaxes(tickformat=".0%", range=[0.83, 1.01])
    fig.update_xaxes(showgrid=True, gridcolor=GRID, range=[0, 0.34])
    show(fig)

with right:
    st.markdown("#### What drives each score")
    st.caption("Composite risk score (0 to 100), split into its five weighted factors.")
    s = risk.sort_values("risk_score")
    sup_full = s.set_index("supplier_id")
    lt = (s["lt_cv"] / 0.35).clip(0, 1) * engine.RISK_WEIGHTS["lt_variability"] * 100
    ot = ((1 - s["otif"]) / 0.15).clip(0, 1) * engine.RISK_WEIGHTS["otif_gap"] * 100
    so = s["sole_source_share"] * engine.RISK_WEIGHTS["sole_source"] * 100
    rg = (s["region_risk"] - 1) / 4 * engine.RISK_WEIGHTS["region"] * 100
    fn = (5 - s["financial_health"]) / 4 * engine.RISK_WEIGHTS["financial"] * 100
    factors = [("Lead time variability", lt), ("OTIF gap", ot), ("Sole sourcing", so),
               ("Region risk", rg), ("Financial health", fn)]
    fig = go.Figure()
    for (label, vals), color in zip(factors, SERIES):
        fig.add_trace(go.Bar(y=s["supplier"], x=vals, name=label, orientation="h",
                             marker=dict(color=color, line=dict(color="white", width=2)),
                             hovertemplate=f"{label}: %{{x:.1f}} pts<extra></extra>"))
    fig.update_layout(barmode="stack")
    style(fig, height=430, xtitle="Risk points")
    fig.update_yaxes(showgrid=False)
    fig.update_xaxes(showgrid=True, gridcolor=GRID, range=[0, 100])
    fig.update_layout(legend=dict(font=dict(size=11)))
    show(fig)

st.markdown("#### Supplier scorecard")
names = dict(zip(parts_df["part_id"], parts_df["part"]))
supplied = {sid: ", ".join(parts_df.loc[(parts_df["supplier_id"] == sid) |
                                        (parts_df["tier2_source"] == sid), "part"])
            for sid in risk["supplier_id"]}
table = pd.DataFrame({
    "Risk": risk["risk_tier"].astype(str).map(lambda t: f"{TIER_ICONS[t]} {t}"),
    "Supplier": risk["supplier"],
    "Tier": risk["tier"],
    "Region": risk["region"],
    "Risk score": risk["risk_score"].round(0),
    "OTIF": risk["otif"],
    "Lead time (days)": risk["lt_mean_days"],
    "Lead time std (days)": risk["lt_std_days"],
    "Annual spend": risk["annual_spend"],
    "Parts": risk["supplier_id"].map(supplied),
})
st.dataframe(table, hide_index=True, width="stretch", column_config={
    "Risk score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
    "OTIF": st.column_config.NumberColumn(format="percent"),
    "Annual spend": st.column_config.NumberColumn(format="dollar"),
})

with st.expander("Scoring methodology"):
    w = engine.RISK_WEIGHTS
    st.markdown(f"""
| Factor | Weight | How it is scaled to 0-1 |
|---|---|---|
| Lead time variability | {w['lt_variability']:.0%} | Coefficient of variation (std / mean), capped at 0.35 |
| OTIF gap | {w['otif_gap']:.0%} | (1 - OTIF) / 0.15, capped at 1 |
| Sole sourcing | {w['sole_source']:.0%} | Share of the supplier's parts with no qualified backup. A tier 2 feeding several boards counts as 1 |
| Region risk | {w['region']:.0%} | 1 (low) to 5 (high) rating for geopolitical, logistics and disaster exposure |
| Financial health | {w['financial']:.0%} | 5 (strong) to 1 (distressed), inverted |

Tiers: Low under 35, Watch 35 to 50, High 50 to 65, Critical 65 and up.
Weights lean toward lead time and delivery because those are what actually stop a line week to week.
""")
sim_note()
