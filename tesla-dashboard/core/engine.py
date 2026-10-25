"""
Core logic: clear-to-build simulation, disruption financials, supplier risk,
and safety stock economics. No Streamlit code lives here, so every number the
dashboard shows can be tested and reproduced on its own.
"""

from dataclasses import dataclass, field
import math

import numpy as np
import pandas as pd

from core.data import WEEKLY_PLAN, WEEKS, suppliers, supplier_spend


# --------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------

@dataclass
class Shock:
    """A supply disruption: inbound for some parts drops by `severity` for a window."""
    part_ids: list = field(default_factory=list)
    severity: float = 0.0        # 0.4 = suppliers ship 40% less than scheduled
    start_week: int = 3
    duration: int = 4


@dataclass
class Mitigation:
    """Spot buys from brokers / expedited air freight to cover part of a shortfall."""
    spot_cover: float = 0.0      # share of the shortfall bought on the spot market
    spot_multiple: float = 3.0   # spot price as a multiple of standard cost
    freight_per_unit: float = 12.0  # premium (air) freight per part, USD
    delay_weeks: int = 1         # spot parts arrive this many weeks after the gap


@dataclass
class Assumptions:
    asp: float = 47000.0             # average selling price per vehicle, USD
    gross_margin: float = 0.18       # automotive gross margin
    fixed_oh_per_vehicle: float = 3200.0  # fixed manufacturing overhead absorbed per car
    recovery: float = 0.60           # share of lost builds recovered next quarter
    carrying_rate: float = 0.25      # annual inventory carrying cost (% of value)


# --------------------------------------------------------------------------
# Clear-to-build simulation
# --------------------------------------------------------------------------

def apply_shock(inbound: pd.DataFrame, shock: Shock, mit: Mitigation):
    """Return (shocked inbound incl. spot receipts, shortfall units, spot units)."""
    shocked = inbound.copy().astype(float)
    shortfall = pd.DataFrame(0.0, index=inbound.index, columns=inbound.columns)
    end = shock.start_week + shock.duration - 1
    for pid in shock.part_ids:
        window = (shocked.index >= shock.start_week) & (shocked.index <= end)
        lost = (inbound.loc[window, pid] * shock.severity).round()
        shocked.loc[window, pid] -= lost
        shortfall.loc[window, pid] = lost

    spot = (shortfall * mit.spot_cover).round()
    # Spot parts land `delay_weeks` later; anything landing past the quarter is dropped
    spot_arrivals = spot.shift(mit.delay_weeks).fillna(0.0)
    shocked += spot_arrivals
    spot_bought = spot_arrivals  # only count what actually arrives and is paid for
    return shocked.round().astype(int), shortfall, spot_bought


def simulate(parts_df: pd.DataFrame, inbound: pd.DataFrame, plan: int = WEEKLY_PLAN):
    """
    Week by week: receive inbound, compute clear-to-build for every part,
    build the minimum (capped at plan), and consume parts.

    Clear-to-build (CTB) for a part = floor(available units / qty per vehicle).
    The line can only build as many cars as its scarcest part allows.
    """
    pid = parts_df["part_id"].tolist()
    qty = parts_df.set_index("part_id")["qty_per_vehicle"]
    inv = parts_df.set_index("part_id")["on_hand"].astype(float).copy()

    weekly, ctb_rows, inv_rows = [], [], []
    for w in inbound.index:
        inv += inbound.loc[w, pid]
        ctb = np.floor(inv / qty)
        built = int(min(plan, ctb.min()))
        binding = ctb.idxmin() if built < plan else None
        inv -= built * qty
        weekly.append({"week": w, "plan": plan, "built": built,
                       "short": plan - built, "binding_part": binding})
        ctb_rows.append(ctb.rename(w))
        inv_rows.append(inv.copy().rename(w))

    weekly = pd.DataFrame(weekly).set_index("week")
    ctb = pd.DataFrame(ctb_rows)
    ctb.index.name = "week"
    inventory = pd.DataFrame(inv_rows)
    inventory.index.name = "week"
    return weekly, ctb, inventory


def days_of_supply(inventory: pd.DataFrame, parts_df: pd.DataFrame,
                   plan: int = WEEKLY_PLAN) -> pd.DataFrame:
    """Ending inventory expressed as days of production it can support (7-day weeks)."""
    daily_need = parts_df.set_index("part_id")["qty_per_vehicle"] * plan / 7
    return inventory / daily_need


def inventory_value(inventory: pd.DataFrame, parts_df: pd.DataFrame) -> pd.Series:
    cost = parts_df.set_index("part_id")["unit_cost"]
    return (inventory * cost).sum(axis=1)


# --------------------------------------------------------------------------
# Financial impact
# --------------------------------------------------------------------------

def run_scenario(parts_df, inbound, shock: Shock, mit: Mitigation, a: Assumptions):
    """Run baseline and shocked simulations and translate the gap into dollars."""
    base_weekly, base_ctb, base_inv = simulate(parts_df, inbound)
    shocked_inbound, shortfall, spot = apply_shock(inbound, shock, mit)
    weekly, ctb, inv = simulate(parts_df, shocked_inbound)

    cost = parts_df.set_index("part_id")["unit_cost"]
    bom_cost = float((parts_df["qty_per_vehicle"] * parts_df["unit_cost"]).sum())

    units_short = int(base_weekly["built"].sum() - weekly["built"].sum())
    units_short = max(units_short, 0)
    permanent_lost = units_short * (1 - a.recovery)

    spot_units = spot.sum()
    ppv = float((spot_units * cost * (mit.spot_multiple - 1)).sum())
    freight = float(spot_units.sum() * mit.freight_per_unit)

    gp_lost = permanent_lost * a.asp * a.gross_margin
    under_absorbed = units_short * a.fixed_oh_per_vehicle

    base_val = inventory_value(base_inv, parts_df)
    scen_val = inventory_value(inv, parts_df)
    stranded = (scen_val - base_val).clip(lower=0)
    stranded_carry = float(stranded.mean() * a.carrying_rate * WEEKS / 52)

    def dio(inv_val, built):
        cogs_per_day = built.sum() * bom_cost / (WEEKS * 7)
        return float(inv_val.mean() / cogs_per_day) if cogs_per_day else float("nan")

    return {
        "base_weekly": base_weekly, "weekly": weekly,
        "base_ctb": base_ctb, "ctb": ctb,
        "base_inventory": base_inv, "inventory": inv,
        "shocked_inbound": shocked_inbound, "shortfall": shortfall, "spot": spot,
        "units_short": units_short,
        "revenue_deferred": units_short * a.asp,
        "permanent_lost_units": permanent_lost,
        "gp_lost": gp_lost,
        "under_absorbed": under_absorbed,
        "ppv": ppv,
        "freight": freight,
        "stranded_peak": float(stranded.max()),
        "stranded_carry": stranded_carry,
        "total_cost": gp_lost + under_absorbed + ppv + freight + stranded_carry,
        "base_dio": dio(base_val, base_weekly["built"]),
        "dio": dio(scen_val, weekly["built"]),
        "bom_cost": bom_cost,
    }


# --------------------------------------------------------------------------
# Supplier risk
# --------------------------------------------------------------------------

RISK_WEIGHTS = {"lt_variability": 0.30, "otif_gap": 0.25, "sole_source": 0.20,
                "region": 0.15, "financial": 0.10}


def supplier_risk(parts_df: pd.DataFrame) -> pd.DataFrame:
    """
    Composite 0-100 supplier risk score. Higher is riskier.
    Each factor is scaled to 0-1, then weighted by RISK_WEIGHTS.
    """
    sup = suppliers().copy()
    spend = supplier_spend(parts_df)
    sup["annual_spend"] = sup["supplier_id"].map(spend).fillna(0.0)

    # Tier 2 spend = value of the tier 1 parts that depend on it
    for s2 in sup.loc[sup["tier"] == 2, "supplier_id"]:
        dep = parts_df[parts_df["tier2_source"] == s2]
        sup.loc[sup["supplier_id"] == s2, "annual_spend"] = float(
            (dep["qty_per_vehicle"] * dep["unit_cost"]).sum() * WEEKLY_PLAN * 52)

    def parts_for(sid):
        return parts_df[(parts_df["supplier_id"] == sid) | (parts_df["tier2_source"] == sid)]

    sup["parts_supplied"] = sup["supplier_id"].apply(lambda s: len(parts_for(s)))
    sup["sole_source_share"] = sup["supplier_id"].apply(
        lambda s: 1.0 if (sup.set_index("supplier_id").loc[s, "tier"] == 2 and len(parts_for(s)) > 1)
        else (parts_for(s)["sole_source"].mean() if len(parts_for(s)) else 0.0))

    sup["lt_cv"] = sup["lt_std_days"] / sup["lt_mean_days"]
    f = pd.DataFrame({
        "lt_variability": (sup["lt_cv"] / 0.35).clip(0, 1),
        "otif_gap": ((1 - sup["otif"]) / 0.15).clip(0, 1),
        "sole_source": sup["sole_source_share"],
        "region": (sup["region_risk"] - 1) / 4,
        "financial": (5 - sup["financial_health"]) / 4,
    })
    sup["risk_score"] = sum(f[k] * w for k, w in RISK_WEIGHTS.items()) * 100
    sup["risk_tier"] = pd.cut(sup["risk_score"], bins=[-1, 35, 50, 65, 101],
                              labels=["Low", "Watch", "High", "Critical"])
    return sup.sort_values("risk_score", ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------
# Safety stock economics
# --------------------------------------------------------------------------

def _phi(z):   # standard normal pdf
    return math.exp(-z * z / 2) / math.sqrt(2 * math.pi)


def _Phi(z):   # standard normal cdf
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def z_for(service_level: float) -> float:
    """Inverse normal cdf by bisection (keeps the app free of a scipy dependency)."""
    lo, hi = -6.0, 6.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if _Phi(mid) < service_level:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def loss_function(z: float) -> float:
    """Standard normal loss L(z): expected units short per unit of std dev."""
    return _phi(z) - z * (1 - _Phi(z))


def safety_stock_economics(part: pd.Series, lt_mean: float, lt_std: float,
                           demand_cv: float, a: Assumptions, service_level: float,
                           review_days: int = 7, plan: int = WEEKLY_PLAN) -> dict:
    """
    Safety stock with both demand and lead-time uncertainty:
        SS = z * sqrt(LT * sd_d^2 + d^2 * sd_LT^2)
    Then price the trade-off: carrying cost of SS vs expected stockout cost.
    """
    d = part["qty_per_vehicle"] * plan / 7               # daily demand, units
    sd_d = d * demand_cv
    sigma = math.sqrt(lt_mean * sd_d ** 2 + d ** 2 * lt_std ** 2)

    z = z_for(service_level)
    ss = max(z, 0) * sigma
    rop = d * lt_mean + ss                               # reorder point
    cycles = 365 / review_days

    exp_short_units = cycles * sigma * loss_function(z)  # part units short per year
    cost_per_vehicle = a.asp * a.gross_margin * (1 - a.recovery) + a.fixed_oh_per_vehicle
    stockout_cost = exp_short_units / part["qty_per_vehicle"] * cost_per_vehicle

    carrying = ss * part["unit_cost"] * a.carrying_rate
    return {
        "z": z, "daily_demand": d, "sigma_lt": sigma, "safety_stock": ss,
        "reorder_point": rop, "cash_in_ss": ss * part["unit_cost"],
        "carrying_cost": carrying, "stockout_cost": stockout_cost,
        "total_cost": carrying + stockout_cost,
        "ss_days": ss / d,
    }


def critical_ratio(part: pd.Series, a: Assumptions, review_days: int = 7) -> float:
    """
    Optimal service level from the marginal trade-off (newsvendor logic):
        stockout probability* = holding cost per unit / (cycles x stockout cost per unit)
    A cheap part that can stop an expensive car gets a ratio very close to 100%.
    """
    h = part["unit_cost"] * a.carrying_rate
    cost_per_vehicle = a.asp * a.gross_margin * (1 - a.recovery) + a.fixed_oh_per_vehicle
    p = h / ((365 / review_days) * cost_per_vehicle / part["qty_per_vehicle"])
    return float(min(max(1 - p, 0.5), 0.99999))


def service_level_curve(part, lt_mean, lt_std, demand_cv, a, levels=None):
    if levels is None:
        # Evenly spaced in z so the high-service tail, where the decisions live, is well covered
        levels = [_Phi(z) for z in np.arange(1.0, 3.75, 0.025)]
    rows = []
    for sl in levels:
        r = safety_stock_economics(part, lt_mean, lt_std, demand_cv, a, sl)
        rows.append({"service_level": sl, **r})
    return pd.DataFrame(rows)


def cash_conversion_cycle(dio: float, dso: float, dpo: float) -> float:
    """CCC = DIO + DSO - DPO. Days between paying suppliers and collecting from customers."""
    return dio + dso - dpo
