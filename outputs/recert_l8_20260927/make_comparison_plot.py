"""Plot selected L8 paths from the same daily CSVs used by the metrics."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


OUT = Path(__file__).resolve().parent
ARMS = {
    "formal_111": "Formal",
    "weight_p0": "Equal-weight slope",
    "gate_011": "Score floor off",
    "gate_101": "Score ceiling off",
    "gate_110": "R² off",
    "ceiling_525_buffer_105": "Ceiling 5.25 + Buffer 1.05",
    "legacy_clean_base": "L3 baseline",
}

series = []
for arm in ARMS:
    daily = pd.read_csv(OUT / "daily" / f"{arm}.csv.gz", usecols=["date", "nav"], parse_dates=["date"])
    daily = daily.rename(columns={"nav": arm}).set_index("date")
    series.append(daily)
frame = pd.concat(series, axis=1)
assert frame.notna().all().all() and len(frame) == 3594
frame.reset_index().to_csv(OUT / "comparison_nav.csv", index=False, float_format="%.16g")

fig, ax = plt.subplots(figsize=(12, 7), dpi=150)
for arm, name in ARMS.items():
    ax.plot(frame.index, frame[arm], label=name, linewidth=2 if arm == "formal_111" else 1.15)
ax.set_yscale("log")
ax.set_title("Six ETF V1.3: L8 complete-combination paper NAV")
ax.set_xlabel("Date")
ax.set_ylabel("NAV, initial capital = 1 (log scale)")
ax.grid(alpha=0.25)
ax.legend(loc="upper left", fontsize=8, ncol=2)
fig.text(0.5, 0.015, "QFQ-labeled historical closes through 2026-09-24; same-close paper fills and 0.10% per leg.",
         ha="center", fontsize=8)
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig(OUT / "comparison_nav.png", dpi=150)
plt.close(fig)
