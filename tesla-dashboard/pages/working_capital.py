import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import engine
from core.ui import (load, inputs, run, money, num, header, sim_note, style, show,
                     BLUE, ORANGE, AQUA, INK_2)

parts_df, _, sup = load()
shock, mit, a = inputs()
r = run(shock, mit, a)
names = dict(zip(parts_df["part_id"], parts_df["part"]))
sup_i = sup.set_index("supplier_id")

header("Working Capital",
       "Safety stock is a finance decision: every extra unit protects the line but ties up cash.")

st.markdown("### Safety stock: carrying cost vs stockout cost")
c1, c2, c3 = st.columns(3)
pid = c1.selectbox("Part", list(names), index=1, format_func=lambda x: names[x])
levels = [0.90, 0.95, 0.97, 0.98, 0.99, 0.995, 0.998, 0.999, 0.9995, 0.9999]
sl = c2.select_slider("Target service level", options=levels, value=0.95,
                      format_func=lambda v: f"{v:.2%}",
                      help="Probability of not running out during a replenishment lead time.")
cv = c3.slider("Demand variability (CV)", 0.05, 0.40, 0.15, 0.05,
               help="Coefficient of variation of daily part demand (std dev / mean).")

part = parts_df.set_index("part_id").loc[pid]
s = sup_i.loc[part["supplier_id"]]
res = engine.safety_stock_economics(part, s["lt_mean_days"], s["lt_std_days"], cv, a, sl)
curve = engine.service_level_curve(part, s["lt_mean_days"], s["lt_std_days"], cv, a)
best = curve.loc[curve["total_cost"].idxmin()]
cr = engine.critical_ratio(part, a)

st.caption(f"Supplier: **{s['supplier']}** ({s['region']}). Lead time {s['lt_mean_days']} days "
           f"(std dev {s['lt_std_days']} days). Unit cost {money(part['unit_cost'])}, "
           f"{part['qty_per_vehicle']} per vehicle.")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Safety stock", f"{num(res['safety_stock'])} units", f"{res['ss_days']:.1f} days of cover",
          delta_color="off",
          help="SS = z x sqrt(LT x demand variance + demand^2 x lead time variance). "
               "Covers both demand swings and late deliveries.")
k2.metric("Reorder point", num(res["reorder_point"]),
          help="Average demand over the lead time + safety stock. Reorder when stock falls here.")
k3.metric("Cash tied up", money(res["cash_in_ss"]), help="Safety stock units x unit cost.")
k4.metric("Annual carrying cost", money(res["carrying_cost"]),
          help=f"Cash tied up x {a.carrying_rate:.0%} carrying rate (capital, storage, obsolescence).")
k5.metric("Expected stockout cost / yr", money(res["stockout_cost"]),
          help="Expected units short per year (normal loss function) converted to lost vehicles, "
               "priced at lost margin plus idle overhead.")

fig = go.Figure()
hover = curve["service_level"].map(lambda v: f"{v:.2%}")
for col, name, color in [("carrying_cost", "Carrying cost", AQUA),
                         ("stockout_cost", "Expected stockout cost", ORANGE),
                         ("total_cost", "Total cost", BLUE)]:
    fig.add_trace(go.Scatter(x=curve["ss_days"], y=curve[col], name=name, mode="lines",
                             line=dict(color=color, width=3 if col == "total_cost" else 2),
                             customdata=hover,
                             hovertemplate=f"{name}: $%{{y:,.0f}}<extra></extra>"))
fig.add_trace(go.Scatter(x=[best["ss_days"]], y=[best["total_cost"]], mode="markers",
                         name=f"Lowest cost ({best['service_level']:.2%} service)",
                         marker=dict(size=16, color=BLUE, symbol="star", line=dict(color="white", width=2)),
                         hoverinfo="skip"))
fig.add_vline(x=res["ss_days"], line=dict(color=INK_2, dash="dot", width=1.5),
              annotation_text=f"Your target ({sl:.2%})", annotation_font=dict(color=INK_2))
fig.update_layout(hovermode="x unified")
style(fig, height=400, xtitle="Safety stock (days of cover)", ytitle="Annual cost")
fig.update_yaxes(tickprefix="$", tickformat="~s", rangemode="tozero")
show(fig)

gap = res["total_cost"] - best["total_cost"]
st.info(
    f"For **{names[pid]}**, total cost bottoms out at **{best['ss_days']:.1f} days** of safety stock "
    f"({best['service_level']:.2%} service level, {money(best['cash_in_ss'])} of cash). "
    f"That matches the **critical ratio** of {cr:.2%}: holding one more unit costs "
    f"{money(part['unit_cost'] * a.carrying_rate)} a year, while running short risks a car worth far more. "
    + (f"Your current target costs **{money(gap)} more per year** than the optimum."
       if gap > 1000 else "Your current target is close to optimal."), icon="🧮")

st.markdown("#### What actually drives the size of the buffer")
st.caption("Because a stopped line costs so much more than holding a part, nearly every part justifies "
           "99%+ availability. What changes from part to part is how many days of buffer that takes, and "
           "that is driven mostly by the supplier's lead time variability, not the part's price. "
           "Making a supplier more predictable frees more cash than lowering service targets.")
rows = []
for p_id, p in parts_df.set_index("part_id").iterrows():
    sp = sup_i.loc[p["supplier_id"]]
    c = engine.service_level_curve(p, sp["lt_mean_days"], sp["lt_std_days"], cv, a)
    b = c.loc[c["total_cost"].idxmin()]
    rows.append({"Part": names[p_id], "Supplier": sp["supplier"], "Unit cost": p["unit_cost"],
                 "Lead time std (days)": sp["lt_std_days"],
                 "Optimal service level": b["service_level"] * 100,
                 "Safety stock (days)": b["ss_days"], "Cash in safety stock": b["cash_in_ss"]})
table = pd.DataFrame(rows).sort_values("Safety stock (days)", ascending=False)
st.dataframe(table, hide_index=True, width="stretch", column_config={
    "Unit cost": st.column_config.NumberColumn(format="dollar"),
    "Optimal service level": st.column_config.NumberColumn(format="%.2f%%"),
    "Safety stock (days)": st.column_config.ProgressColumn(
        min_value=0, max_value=float(table["Safety stock (days)"].max()), format="%.1f"),
    "Cash in safety stock": st.column_config.NumberColumn(format="dollar"),
})

st.divider()
st.markdown("### Cash conversion cycle")
st.caption("CCC = DIO + DSO - DPO. The number of days cash is tied up between paying suppliers and "
           "collecting from customers. A negative CCC means suppliers are financing operations.")
d1, d2 = st.columns(2)
dso = d1.number_input("Days sales outstanding (DSO)", 0.0, 90.0, 15.0, 1.0,
                      help="How fast customers pay. Direct-to-consumer car sales collect quickly.")
dpo = d2.number_input("Days payables outstanding (DPO)", 0.0, 120.0, 60.0, 1.0,
                      help="How long you take to pay suppliers.")
base_ccc = engine.cash_conversion_cycle(r["base_dio"], dso, dpo)
scen_ccc = engine.cash_conversion_cycle(r["dio"], dso, dpo)
m1, m2, m3 = st.columns(3)
m1.metric("DIO (tracked BOM)", f"{r['dio']:.1f} days", f"{r['dio'] - r['base_dio']:+.1f} vs baseline",
          delta_color="inverse")
m2.metric("Cash conversion cycle", f"{scen_ccc:.1f} days", f"{scen_ccc - base_ccc:+.1f} vs baseline",
          delta_color="inverse")
daily_cogs = r["weekly"]["built"].sum() * r["bom_cost"] / (len(r["weekly"]) * 7)
m3.metric("Extra cash tied up by the shortage", money(max(r["dio"] - r["base_dio"], 0) * daily_cogs),
          help="Change in DIO x daily COGS on the tracked BOM.")
sim_note()
