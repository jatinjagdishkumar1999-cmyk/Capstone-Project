"""Part 2 / Task 11 — two Matplotlib charts, regenerated from the raw CSVs on every run.

Run:  python analysis/visualize.py      (writes visualizations/*.png)
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from clean_and_eda import ROOT, run  # noqa: E402

OUT = ROOT / "visualizations"
OUT.mkdir(exist_ok=True)

res = run(verbose=False, write_findings=False)  # same pipeline, same numbers, no side effects
rates = dict(sorted(res["pay_rates"].items(), key=lambda kv: kv[1], reverse=True))
monthly = res["monthly_fix"]  # outlier-corrected series

RISK, NEUTRAL, INK = "#C8442F", "#8A9BA8", "#222222"


def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(colors=INK)
    ax.yaxis.grid(True, alpha=0.25)
    ax.set_axisbelow(True)


# 1) Return rate by payment method -------------------------------------------
fig, ax = plt.subplots(figsize=(7, 4.5), dpi=150)
names, vals = list(rates), list(rates.values())
bars = ax.bar(names, vals, color=[RISK if n == "COD" else NEUTRAL for n in names], width=0.55)
for b, v in zip(bars, vals):
    ax.text(b.get_x() + b.get_width() / 2, v + 0.8, f"{v:.1f}%", ha="center", fontsize=11, color=INK, fontweight="bold")
ratio = rates["COD"] / rates["CARD"]
ax.set_title(f"COD Returns at {rates['COD']:.1f}% — {ratio:.0f}x Card", loc="left", fontsize=14, fontweight="bold", color=INK)
ax.set_xlabel("Payment method (cleaned)")
ax.set_ylabel("Return rate (%)")
ax.set_ylim(0, max(vals) * 1.18)
style(ax)
fig.tight_layout()
fig.savefig(OUT / "return_rate_by_payment.png")
plt.close(fig)

# 2) Outlier-corrected monthly revenue ---------------------------------------
peak = monthly.idxmax()
fig, ax = plt.subplots(figsize=(7, 4.5), dpi=150)
ax.plot(monthly.index, monthly.values, marker="o", color=NEUTRAL, linewidth=2)
ax.plot([peak], [monthly[peak]], marker="o", markersize=10, color=RISK)
ax.annotate(f"Peak {peak}\n₹{monthly[peak]:,.2f}", (peak, monthly[peak]), textcoords="offset points",
            xytext=(12, -4), fontsize=10, color=INK)
month_name = {"01": "January", "02": "February", "03": "March", "04": "April", "05": "May", "06": "June"}[peak[-2:]]
ax.set_title(f"{month_name} Is the True Revenue Peak (Outliers Excluded)", loc="left", fontsize=14, fontweight="bold", color=INK)
ax.set_xlabel("Month")
ax.set_ylabel("Revenue (₹)")
ax.set_ylim(0, monthly.max() * 1.2)
style(ax)
fig.tight_layout()
fig.savefig(OUT / "monthly_revenue_trend.png")
plt.close(fig)

print("Saved:", *(p.relative_to(ROOT) for p in sorted(OUT.glob("*.png"))))
