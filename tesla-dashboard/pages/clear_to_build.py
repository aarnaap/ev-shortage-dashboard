import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import engine
from core.data import WEEKLY_PLAN
from core.ui import (load, inputs, run, num, header, scenario_banner, sim_note, style, show,
                     BLUE, CRITICAL, INK_2, MUTED)

parts_df, inbound, sup = load()
shock, mit, a = inputs()
r = run(shock, mit, a)
names = dict(zip(parts_df["part_id"], parts_df["part"]))
p = parts_df.set_index("part_id")

header("Clear to Build",
       "Given what is on hand plus what arrives this week, how many cars can we actually build?")
scenario_banner(shock, parts_df)

with st.expander("How clear-to-build works"):
    st.markdown(
        "For each part: **CTB = floor(units available / quantity per vehicle)**. "
        "The line can only build as many cars as its scarcest part allows, so the week's output is "
        "the minimum CTB across the bill of materials, capped at the build plan. The part with the "
        "lowest CTB is the **binding constraint**. Fixing any other part does not add a single car.")

default_week = shock.start_week + min(shock.duration, 3) - 1 if shock.part_ids else 1
week = st.slider("Week", 1, len(r["ctb"]), min(default_week, len(r["ctb"])))

ctb = r["ctb"].loc[week]
built = int(r["weekly"].loc[week, "built"])
binding = r["weekly"].loc[week, "binding_part"]
binding = binding if isinstance(binding, str) else None

c1, c2, c3, c4 = st.columns(4)
c1.metric("Build plan", num(WEEKLY_PLAN))
c2.metric("Clear to build", num(min(ctb.min(), WEEKLY_PLAN)),
          f"{built - WEEKLY_PLAN:,} vs plan" if built < WEEKLY_PLAN else "On plan",
          delta_color="normal" if built < WEEKLY_PLAN else "off")
c3.metric("Binding constraint", names[binding] if binding else "None",
          help="The part with the lowest CTB this week.")
c4.metric("Parts below plan", int((ctb < WEEKLY_PLAN).sum()))

st.markdown(f"#### Clear-to-build by part, week {week}")
cap = WEEKLY_PLAN * 2.5
df = pd.DataFrame({"part": [names[i] for i in ctb.index], "ctb": ctb.values,
                   "sole": [p.loc[i, "sole_source"] for i in ctb.index]}).sort_values("ctb", ascending=False)
colors = [CRITICAL if v < WEEKLY_PLAN else BLUE for v in df["ctb"]]
fig = go.Figure(go.Bar(
    x=np.minimum(df["ctb"], cap), y=df["part"], orientation="h", marker_color=colors,
    customdata=np.stack([df["ctb"], np.where(df["sole"], "Sole source", "Multi source")], axis=1),
    hovertemplate="%{y}<br>CTB: %{customdata[0]:,.0f} vehicles<br>%{customdata[1]}<extra></extra>"))
fig.add_vline(x=WEEKLY_PLAN, line=dict(color=INK_2, width=2, dash="dot"),
              annotation_text=f"Plan {WEEKLY_PLAN:,}", annotation_position="top",
              annotation_font=dict(color=INK_2))
style(fig, height=470, legend=False, xtitle="Vehicles the part can support")
fig.update_xaxes(range=[0, cap], showgrid=True, gridcolor="#e6e5e1")
fig.update_yaxes(showgrid=False)
show(fig)
st.caption("🔴 Red bars are below plan and limit output. Bars are capped at 2.5x plan for readability; "
           "hover for the exact figure.")

st.markdown("#### Days of supply heatmap")
st.caption("Ending inventory in days of production. Red means the part is running short; "
           "blue means it is piling up. Gray is roughly the half-week safety stock target.")
dos = engine.days_of_supply(r["inventory"], parts_df).T
dos.index = [names[i] for i in dos.index]
target = 3.5
fig = go.Figure(go.Heatmap(
    z=dos.values, x=[f"W{w}" for w in dos.columns], y=dos.index,
    zmin=0, zmid=target, zmax=target * 3,
    colorscale=[[0, "#d03b3b"], [0.33, "#f0efec"], [1, "#184f95"]],
    xgap=2, ygap=2, text=np.round(dos.values, 1), texttemplate="%{text}",
    textfont=dict(size=11),
    hovertemplate="%{y}<br>%{x}: %{z:.1f} days<extra></extra>",
    colorbar=dict(title="Days", thickness=12)))
style(fig, height=520, legend=False)
fig.update_xaxes(side="top")
fig.update_yaxes(autorange="reversed", showgrid=False)
show(fig)

st.markdown(f"#### Part detail, week {week}")
inv_prev = r["inventory"].loc[week - 1] if week > 1 else p["on_hand"]
detail = pd.DataFrame({
    "Part": [names[i] for i in ctb.index],
    "Qty / vehicle": p.loc[ctb.index, "qty_per_vehicle"].values,
    "Opening stock": inv_prev.loc[ctb.index].values,
    "Inbound": r["shocked_inbound"].loc[week, ctb.index].values,
    "Needed for plan": (p.loc[ctb.index, "qty_per_vehicle"] * WEEKLY_PLAN).values,
    "CTB (vehicles)": ctb.values,
    "Sole source": np.where(p.loc[ctb.index, "sole_source"], "Yes", "No"),
}).sort_values("CTB (vehicles)")
detail["Gap to plan"] = np.minimum(detail["CTB (vehicles)"] - WEEKLY_PLAN, 0)
st.dataframe(detail, hide_index=True, width="stretch",
             column_config={c: st.column_config.NumberColumn(format="%d")
                            for c in ["Opening stock", "Inbound", "Needed for plan",
                                      "CTB (vehicles)", "Gap to plan"]})
sim_note()
