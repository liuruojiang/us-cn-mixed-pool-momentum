from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import PercentFormatter


RUN_DIR = Path(__file__).resolve().parent
frame = pd.read_csv(RUN_DIR / "window_metrics.csv").sort_values("lookback")

windows = [
    ("full", "Full"),
    ("last_10y", "10Y"),
    ("last_5y", "5Y"),
    ("last_3y", "3Y"),
    ("last_1y", "1Y"),
]

fig, axes = plt.subplots(2, 1, figsize=(13, 8.5), sharex=True, constrained_layout=True)
for suffix, display in windows:
    axes[0].plot(frame["lookback"], frame[f"ann_return_{suffix}"], marker="o", markersize=2.8, linewidth=1.5, label=display)
    axes[1].plot(frame["lookback"], frame[f"max_dd_{suffix}"], marker="o", markersize=2.8, linewidth=1.5, label=display)

for axis in axes:
    axis.axvspan(24, 33, color="grey", alpha=0.10)
    axis.axvline(25, color="black", linestyle="--", linewidth=1.2)
    axis.grid(True, alpha=0.22)
    axis.yaxis.set_major_formatter(PercentFormatter(1.0))

axes[0].set_title("Sub-D V1.1 Lookback Sensitivity: 10-50 Trading Days")
axes[0].set_ylabel("Annualized return")
axes[0].legend(ncol=5, loc="upper right", frameon=False)
axes[0].annotate("Current 25D", xy=(25, frame.loc[frame.lookback.eq(25), "ann_return_full"].iat[0]), xytext=(26.5, 0.08), arrowprops={"arrowstyle": "->"})

axes[1].set_ylabel("Max drawdown")
axes[1].set_xlabel("Momentum lookback (trading days)")
axes[1].set_xticks(range(10, 51, 5))
axes[1].annotate("Current 25D", xy=(25, frame.loc[frame.lookback.eq(25), "max_dd_full"].iat[0]), xytext=(26.5, -0.72), arrowprops={"arrowstyle": "->"})

fig.savefig(RUN_DIR / "lookback_10_50_sensitivity.png", dpi=180)
