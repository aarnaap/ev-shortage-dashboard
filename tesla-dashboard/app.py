"""
Shortage to Cash Impact: a PCBA supply risk dashboard.

Run locally:  streamlit run app.py

app.py is the router. It runs on every page, so the scenario controls in the
sidebar live here and stay set as you move between pages.
"""

import streamlit as st

from core.ui import load

st.set_page_config(page_title="Shortage to Cash Impact", page_icon="📉", layout="wide")

parts_df, _, _ = load()
names = dict(zip(parts_df["part_id"], parts_df["part"]))

with st.sidebar:
    st.markdown("### Shortage scenario")
    st.multiselect("Part(s) in shortage", options=list(names), default=["P102"],
                   format_func=lambda p: names[p], key="shock_parts",
                   help="The part(s) whose supplier inbound gets cut.")
    st.slider("Severity (% of inbound lost)", 0, 90, 50, 5, key="severity")
    st.slider("Start week", 1, 13, 3, key="start_week")
    st.slider("Duration (weeks)", 1, 8, 4, key="duration")

    st.markdown("### Mitigation")
    st.slider("Spot buy cover (% of shortfall)", 0, 100, 30, 10, key="spot_cover",
              help="Share of the missing parts bought from brokers and air-freighted in.")
    st.slider("Spot price multiple", 1.0, 8.0, 3.0, 0.5, key="spot_multiple",
              help="Broker price as a multiple of standard cost. 3x to 10x was common in 2021-22.")
    st.number_input("Premium freight per part ($)", 0.0, 200.0, 12.0, 1.0, key="freight")
    st.slider("Spot lead time (weeks)", 0, 3, 1, key="delay")

    with st.expander("Financial assumptions"):
        st.number_input("Average selling price ($)", 20000.0, 150000.0, 47000.0, 1000.0, key="asp")
        st.slider("Automotive gross margin (%)", 5, 35, 18, key="gm")
        st.number_input("Fixed overhead per vehicle ($)", 0.0, 15000.0, 3200.0, 100.0, key="fixed_oh",
                        help="Plant overhead absorbed by each car built. Idle capacity still costs this.")
        st.slider("Lost builds recovered next quarter (%)", 0, 100, 60, 5, key="recovery")
        st.slider("Inventory carrying rate (% per year)", 5, 40, 25, key="carry")

pages = [
    st.Page("pages/overview.py", title="Executive Overview", icon="📊", default=True),
    st.Page("pages/clear_to_build.py", title="Clear to Build", icon="🏭"),
    st.Page("pages/suppliers.py", title="Supplier Risk", icon="🌐"),
    st.Page("pages/scenario.py", title="Shortage P&L Impact", icon="💸"),
    st.Page("pages/working_capital.py", title="Working Capital", icon="🏦"),
]
st.navigation(pages).run()
