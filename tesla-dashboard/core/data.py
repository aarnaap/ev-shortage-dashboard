"""
Simulated supply chain data for one EV assembly line over a 13-week quarter.

Everything here is SIMULATED. Part names, suppliers, costs, and quantities are
illustrative assumptions built to behave like a real automotive supply base.
They are not Tesla data. The seed is fixed so the dashboard is reproducible.
"""

import numpy as np
import pandas as pd

WEEKS = 13            # one fiscal quarter
WEEKLY_PLAN = 5000    # vehicles scheduled per week (the build plan)
SEED = 42


def suppliers() -> pd.DataFrame:
    """Supplier master. Tier 1 ships directly to the line; tier 2 supplies a tier 1."""
    rows = [
        # id,   name,                           region,     tier, otif,  lt_mean, lt_std, fin_health, region_risk
        ("S01", "Hsinchu Precision Electronics", "Taiwan",    1, 0.91,  56, 14, 4, 4),
        ("S02", "Bajio Circuit Works",           "Mexico",    1, 0.94,  21,  4, 3, 2),
        ("S03", "Pearl River EMS",               "China",     1, 0.89,  42, 11, 4, 4),
        ("S04", "Penang Sensing Systems",        "Malaysia",  1, 0.93,  35,  7, 4, 3),
        ("S06", "Great Lakes Cell Co.",          "USA",       1, 0.96,  14,  2, 5, 1),
        ("S07", "Monterrey Harness Group",       "Mexico",    1, 0.92,  18,  5, 3, 2),
        ("S08", "Ningbo Automotive Glass",       "China",     1, 0.95,  38,  6, 4, 4),
        ("S10", "Midwest Seating & Thermal",     "USA",       1, 0.97,   7,  1, 4, 1),
        ("S00", "In-house Drive Unit Line",      "USA",       1, 0.99,   3,  1, 5, 1),
        ("S09", "Lumen Semiconductor Fab",       "Taiwan",    2, 0.86,  98, 28, 4, 4),
    ]
    cols = ["supplier_id", "supplier", "region", "tier", "otif",
            "lt_mean_days", "lt_std_days", "financial_health", "region_risk"]
    return pd.DataFrame(rows, columns=cols)


def parts() -> pd.DataFrame:
    """
    Tracked bill of materials (BOM). Only constraint-relevant parts are tracked,
    which is how real shortage teams work: you watch the parts that can stop the line.

    tier2_source shows the hidden dependency: which chip fab sits underneath a PCBA.
    """
    rows = [
        # id,   part,                         category,     qty, unit_cost, supplier, sole, tier2,  weeks_on_hand
        ("P101", "Autopilot Compute PCBA",     "PCBA",          1, 1450, "S01", True,  "S09", 1.1),
        ("P102", "Body Controller PCBA",       "PCBA",          3,   85, "S02", True,  "S09", 0.9),
        ("P103", "Battery Management PCBA",    "PCBA",          1,  210, "S03", True,  "S09", 1.2),
        ("P104", "Inverter Gate Driver PCBA",  "PCBA",          1,  160, "S01", False, "S09", 1.3),
        ("P105", "Infotainment PCBA",          "PCBA",          1,  380, "S04", False, None,  2.8),
        ("P106", "Seat Control Module PCBA",   "PCBA",          4,   38, "S02", False, "S09", 1.0),
        ("P107", "Charge Port Controller PCBA","PCBA",          1,   45, "S03", True,  None,  3.0),
        ("P201", "Camera & Radar Suite",       "Sensors",       1,  290, "S04", True,  None,  2.4),
        ("P301", "Battery Cell Module",        "Battery",       4, 1900, "S06", False, None,  1.2),
        ("P401", "Rear Drive Unit",            "Powertrain",    1, 2600, "S00", False, None,  0.8),
        ("P501", "High-Voltage Wiring Harness","Electrical",    1,  650, "S07", True,  None,  1.5),
        ("P601", "Panoramic Glass Roof",       "Body",          1,  420, "S08", True,  None,  3.2),
        ("P701", "Seat Assembly",              "Interior",      5,  310, "S10", False, None,  0.6),
        ("P801", "Heat Pump Assembly",         "Thermal",       1,  520, "S10", False, None,  1.0),
    ]
    cols = ["part_id", "part", "category", "qty_per_vehicle", "unit_cost",
            "supplier_id", "sole_source", "tier2_source", "weeks_on_hand"]
    df = pd.DataFrame(rows, columns=cols)
    weekly_need = WEEKLY_PLAN * df["qty_per_vehicle"]
    df["on_hand"] = (weekly_need * df["weeks_on_hand"]).round().astype(int)
    df["safety_stock"] = (weekly_need * 0.5).round().astype(int)   # half a week of cover
    return df.drop(columns="weeks_on_hand")


def inbound_schedule(parts_df: pd.DataFrame) -> pd.DataFrame:
    """
    Scheduled inbound receipts per part per week (rows = week 1..13, cols = part_id).
    Suppliers ship roughly to plan with noise driven by their OTIF performance.
    """
    rng = np.random.default_rng(SEED)
    sup = suppliers().set_index("supplier_id")
    data = {}
    for _, p in parts_df.iterrows():
        need = WEEKLY_PLAN * p["qty_per_vehicle"]
        otif = sup.loc[p["supplier_id"], "otif"]
        # Less reliable suppliers ship with more variance, centred near plan
        noise = rng.normal(1.01, (1 - otif) * 0.5, WEEKS)
        data[p["part_id"]] = np.maximum(0, need * noise).round().astype(int)
    df = pd.DataFrame(data, index=pd.RangeIndex(1, WEEKS + 1, name="week"))
    return df


def supplier_spend(parts_df: pd.DataFrame) -> pd.Series:
    """Annualised spend by tier 1 supplier (52 weeks at plan)."""
    spend = parts_df["qty_per_vehicle"] * parts_df["unit_cost"] * WEEKLY_PLAN * 52
    return spend.groupby(parts_df["supplier_id"]).sum()
