"""Part 2 — Pandas data wrangling & EDA for the Mamaearth returns pipeline.

Run from anywhere:  python analysis/clean_and_eda.py
Reads  : data/orders.csv, data/customers.csv, data/products.csv  (raw, never edited)
Writes : narrator/findings.json   (Part 3 input — generated here, never hand-typed)
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
FINDINGS_PATH = ROOT / "narrator" / "findings.json"


def band(r: float) -> str:
    """Taught correlation-strength bands on |r|."""
    a = abs(r)
    if a < 0.2:
        return "negligible"
    if a < 0.4:
        return "weak"
    if a < 0.7:
        return "moderate"
    return "strong"


def run(verbose: bool = True, write_findings: bool = True) -> dict:
    say = print if verbose else (lambda *a, **k: None)

    # ---------------------------------------------------------------- Task 1
    say("=== Task 1: Load and inspect ===")
    orders = pd.read_csv(DATA / "orders.csv")
    customers = pd.read_csv(DATA / "customers.csv")
    products = pd.read_csv(DATA / "products.csv")
    say("orders.shape    :", orders.shape)
    say("customers.shape :", customers.shape)
    say("products.shape  :", products.shape)

    # Raw revenue (before any cleaning) — computed here so the reconciliation
    # in Task 5 uses a number this script produced, not a pasted one.
    raw = orders.merge(products, on="product_id")
    raw_total = (raw["quantity"] * raw["price"] * (1 - raw["discount_pct"].fillna(0) / 100)).sum()

    # ---------------------------------------------------------------- Task 2
    say("\n=== Task 2: Standardize payment_method casing ===")
    say("Raw unique values   :", sorted(orders["payment_method"].unique()),
        f"({orders['payment_method'].nunique()} distinct)")
    orders["payment_method"] = orders["payment_method"].str.strip().str.upper()
    say("Clean unique values :", sorted(orders["payment_method"].unique()),
        f"({orders['payment_method'].nunique()} distinct)")
    say("Counts:\n" + orders["payment_method"].value_counts().to_string())

    # ---------------------------------------------------------------- Task 3
    say("\n=== Task 3: Remove duplicate orders ===")
    key = ["customer_id", "product_id", "order_date", "quantity",
           "discount_pct", "payment_method", "rating", "returned"]
    dup_mask = orders.duplicated(subset=key, keep="first")
    dropped = orders[dup_mask].copy()
    say("Duplicates flagged :", int(dup_mask.sum()))
    say("Dropped order_ids  :", dropped["order_id"].tolist())
    orders_clean = orders[~dup_mask].reset_index(drop=True)
    say("orders_clean.shape :", orders_clean.shape)

    # ---------------------------------------------------------------- Task 4
    say("\n=== Task 4: Impute missing values ===")
    n_disc = int(orders_clean["discount_pct"].isna().sum())
    n_rate = int(orders_clean["rating"].isna().sum())
    median_rating = orders_clean["rating"].median()
    say(f"discount_pct NaN rows : {n_disc}  -> fill with 0 (no promo code applied)")
    say(f"rating median (non-null, deduplicated frame): {median_rating}")
    say(f"rating NaN rows       : {n_rate}  -> fill with median {median_rating}")
    orders_clean["discount_pct"] = orders_clean["discount_pct"].fillna(0)
    orders_clean["rating"] = orders_clean["rating"].fillna(median_rating)
    say("Nulls after imputing:", orders_clean[["discount_pct", "rating"]].isnull().sum().to_dict())

    # ---------------------------------------------------------------- Task 5
    say("\n=== Task 5: Merge and reconcile against Part 1 ===")
    df = (orders_clean.merge(products, on="product_id", how="left")
                      .merge(customers, on="customer_id", how="left"))
    df["order_value"] = df["quantity"] * df["price"] * (1 - df["discount_pct"] / 100)
    clean_total = df["order_value"].sum()
    say("merged shape                    :", df.shape)
    say(f"Cleaned total order_value (175 rows): Rs {clean_total:,.2f}")

    d = dropped.merge(products, on="product_id", how="left")
    dropped_value = (d["quantity"] * d["price"] * (1 - d["discount_pct"].fillna(0) / 100)).sum()
    delta = raw_total - clean_total
    say(f"Raw total (180 rows, = Part 1 report a): Rs {raw_total:,.2f}")
    say(f"Delta raw - clean                    : Rs {delta:,.2f}")
    say(f"Sum of the 5 dropped rows (independent): Rs {dropped_value:,.2f}")
    assert abs(delta - dropped_value) < 0.005, "reconciliation failed"
    say(
        "\nRECONCILIATION NOTE: The cleaned revenue of Rs {c:,.2f} is Rs {x:,.2f} lower than the raw "
        "Part 1 total of Rs {r:,.2f}. This delta is entirely explained by the 5 double-submitted duplicate "
        "orders ({ids}) removed in Task 3, whose combined order_value, summed independently, is Rs {x:,.2f}. "
        "It is not caused by imputation: filling discount_pct with 0 matches Part 1's COALESCE(discount_pct, 0), "
        "and filling rating changes no order_value, so neither alters any revenue total.".format(
            c=clean_total, x=dropped_value, r=raw_total, ids=", ".join(dropped["order_id"])))

    # ---------------------------------------------------------------- Task 6
    say("\n=== Task 6: IQR outlier detection on quantity ===")
    q1, q3 = df["quantity"].quantile(0.25), df["quantity"].quantile(0.75)
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    say(f"Q1={q1}  Q3={q3}  IQR={iqr}  lower={lower}  upper={upper}")
    df["is_outlier"] = (df["quantity"] < lower) | (df["quantity"] > upper)
    outliers = df[df["is_outlier"]]
    say(f"Outlier rows ({len(outliers)}) — flagged, NOT dropped:")
    say(outliers[["order_id", "order_date", "quantity", "order_value"]].to_string(index=False))

    # ---------------------------------------------------------------- Task 7
    say("\n=== Task 7: Does COD have a higher return rate? ===")
    say("HYPOTHESIS: COD orders have a higher return rate than prepaid (CARD / UPI) orders.")
    pay = df.groupby("payment_method")["returned"].agg(["count", "mean"])
    pay["return_rate_pct"] = (pay["mean"] * 100).round(1)
    say(pay.to_string())
    pay_rates = pay["return_rate_pct"].to_dict()
    confirmed = pay_rates["COD"] > max(pay_rates["CARD"], pay_rates["UPI"])
    say(f"VERDICT: {'Confirmed' if confirmed else 'Rejected'} "
        f"(COD {pay_rates['COD']}% vs CARD {pay_rates['CARD']}% and UPI {pay_rates['UPI']}%)")

    # ---------------------------------------------------------------- Task 8
    say("\n=== Task 8: Multi-level segmentation (payment_method x city_tier) ===")
    seg = df.groupby(["payment_method", "city_tier"])["returned"].agg(["count", "mean"])
    seg["return_rate_pct"] = (seg["mean"] * 100).round(1)
    say(seg.to_string())
    (top_pm, top_tier), top_row = seg["return_rate_pct"].idxmax(), seg.loc[seg["return_rate_pct"].idxmax()]
    top_rate = float(top_row["return_rate_pct"])
    say(f"HIGHEST-RISK SEGMENT: {top_pm} + Tier-{top_tier} cities at {top_rate}% "
        f"({int(top_row['count'])} orders)")
    for t in (1, 2):
        r = seg.loc[("COD", t)]
        say(f"  COD Tier-{t}: {int(r['count'])} orders at {r['return_rate_pct']}%")
    say("COD risk is NOT uniform across tiers — a single blended COD rate hides where it concentrates.")

    # ---------------------------------------------------------------- Task 9
    say("\n=== Task 9: Correlation analysis ===")
    cols = ["rating", "returned", "discount_pct", "quantity"]
    corr = df[cols].corr()
    say(corr.round(3).to_string())
    pairs = []
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            r = corr.loc[a, b]
            pairs.append((a, b, r))
            say(f"  {a:>12} vs {b:<12} r={r:+.3f}  -> {band(r)}")
    assert all(band(r) == "negligible" for _, _, r in pairs)
    r_dr = corr.loc["discount_pct", "returned"]
    say(f"HYPOTHESIS 'higher discounts reduce returns': Busted "
        f"(r={r_dr:+.3f}, {band(r_dr)}).")

    # ---------------------------------------------------------------- Task 10
    say("\n=== Task 10: Outlier-corrected monthly revenue ===")
    df["order_date"] = pd.to_datetime(df["order_date"])
    df["year_month"] = df["order_date"].dt.to_period("M").astype(str)
    monthly_all = df.groupby("year_month")["order_value"].sum().round(2)
    monthly_fix = df[~df["is_outlier"]].groupby("year_month")["order_value"].sum().round(2)
    say("(1) INCLUDING the two outlier orders:\n" + monthly_all.to_string())
    say("(2) EXCLUDING them (outlier-corrected):\n" + monthly_fix.to_string())
    apparent_month, true_month = monthly_all.idxmax(), monthly_fix.idxmax()
    out_dates = ", ".join(f"{r.order_id} on {r.order_date:%Y-%m-%d}" for r in df[df['is_outlier']].itertuples())
    say(f"\nINTERPRETATION: {apparent_month}'s apparent lead is an artifact of the two bulk orders "
        f"landing in that month ({out_dates}). Once they are excluded, {true_month} "
        f"(Rs {monthly_fix[true_month]:,.2f}) is the genuine peak month.")

    # ---------------------------------------------------------------- findings
    findings = {
        "cleaned_total_revenue_inr": round(float(clean_total), 2),
        "raw_total_revenue_inr": round(float(raw_total), 2),
        "duplicate_reconciliation_delta_inr": round(float(delta), 2),
        "return_rate_by_payment": {k: float(v) for k, v in pay_rates.items()},
        "highest_risk_segment": {"payment_method": top_pm, "city_tier": int(top_tier),
                                 "return_rate_pct": top_rate},
        "true_peak_month": {"month": true_month, "revenue_inr": float(monthly_fix[true_month])},
        "outlier_inflated_month": {"month": apparent_month,
                                   "apparent_revenue_inr": float(monthly_all[apparent_month]),
                                   "corrected_revenue_inr": float(monthly_fix[apparent_month])},
    }
    if write_findings:
        FINDINGS_PATH.parent.mkdir(exist_ok=True)
        FINDINGS_PATH.write_text(json.dumps(findings, indent=2) + "\n")
        say(f"\nWrote {FINDINGS_PATH.relative_to(ROOT)} (feeds Part 3).")

    return {"df": df, "pay_rates": pay_rates, "monthly_fix": monthly_fix,
            "monthly_all": monthly_all, "findings": findings}


if __name__ == "__main__":
    run()
