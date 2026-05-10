# Sub-D Six ETF V1.1 Notes - 2026-05-09

## Version Definition

V1.1 is the six-ETF weighted log-slope strategy with two execution/risk rules added on top of the current V1.0 baseline.

Baseline held constant:

- Pool: `159915.SZ`, `159941.SZ`, `513030.SH`, `513520.SH`, `159985.SZ`, `518880.SH`
- Signal: 25-day weighted log-price slope, annualized as `exp(slope * 252) - 1`
- Eligibility: `0 < score < 5`, `R2 >= 0.20`
- Execution model: close-confirmed / close-executed daily path
- Target volatility: `25%`, max leverage `1.5x`
- One-way cost: `0.10%`
- Asset stop: off
- Top1 switch buffer: `1.05`
- Evaluation window: 2020-01-02 to 2026-05-08, with full warmup from 2010-01-01

V1.1 additions:

1. New Top1 staged entry: when switching into any newly selected Top1 asset, enter 50% first, then fill the remaining 50% after the first down close, defined as `curr_close < prev_close`.
2. MA60 bias overheat filter: if the active holding has `price / MA60 - 1 >= 20%` and the A-style bias momentum is positive, set exposure to cash on the next close-to-close segment. Recover when bias falls to `18%` or the same-side condition no longer holds.

This staged-entry rule is intentionally broader than the current A-strategy source rule. A-source `CN_ENTRY_INITIAL_FRACTION = 0.5` only applies when entering from cash; V1.1 applies it to every newly selected Top1 asset.

## Measured Result

Source command:

```powershell
python .\run_subd_six_etf_v1_1.py
```

Main comparison:

| Version | Window | Annual Return | Max DD | Sharpe | Vol |
|---|---:|---:|---:|---:|---:|
| V1.0 | from 2020 | 54.60% | -21.36% | 1.706 | 27.78% |
| V1.1 | from 2020 | 59.21% | -18.11% | 1.906 | 26.20% |
| V1.0 | 5Y | 54.19% | -21.36% | 1.699 | 27.72% |
| V1.1 | 5Y | 64.77% | -18.11% | 2.076 | 25.64% |
| V1.0 | 3Y | 88.57% | -19.02% | 2.317 | 29.19% |
| V1.1 | 3Y | 102.26% | -16.55% | 2.769 | 26.73% |
| V1.0 | 1Y | 83.85% | -15.20% | 2.420 | 26.66% |
| V1.1 | 1Y | 96.43% | -12.75% | 2.853 | 24.75% |

V1.1 event counts from 2020:

- Staged initial entries: 187
- Staged fills after first down close: 151
- Half-position waiting days: 345
- Top1 switch buffer blocks: 17
- MA60 bias overheat triggers: 10
- Overheat defense days: 17
- Trades: 359

Durable outputs:

- `outputs/subd_six_etf_v1_1_20260509_summary.csv`
- `outputs/subd_six_etf_v1_1_20260509_daily.csv`
- `outputs/subd_six_etf_v1_1_20260509_sources.csv`
- `outputs/subd_six_etf_v1_1_20260509_data_quality.csv`

## Verification

- `python -m py_compile .\run_subd_six_etf_v1_1.py .\poe_subd_six_etf_v1_1_bot.py` passed.
- V1.1 metrics use the selected `switch_buffer=1.05` setting.
- V1.0 comparison is explicitly locked to `switch_buffer=1.00`, so the baseline remains the original full-entry reference.
- Daily output has 6,992 rows, 2 scenarios, no duplicate `scenario/date`, and no missing `return/nav`.

Data source:

- `akshare.fund_etf_hist_sina`, raw/unadjusted close as served by Sina.
- Current data range reaches 2026-05-08.
- Data-quality caveat: `159941.SZ` has a 74.66% daily move on 2022-07-05 in the raw Sina series. Before treating V1.1 as production-ready, validate this against an adjusted or independent source.

## Optimization Directions

Priority 1: V1.1 parameter robustness.

- Scan staged-entry initial fraction around `40% / 50% / 60% / 70%`.
- Scan fill trigger variants: first down close, first `-0.5%` close, first `-1.0%` close, or timeout after `3/5/10` trading days.
- Scan overheat bands around `18/16`, `20/18`, `22/20`, and `24/22` after staged entry, not on the old baseline.
- Judge by `1Y/3Y/5Y/from_2020`, not only full sample.

Priority 2: target-vol and R2 interaction after V1.1.

- Re-scan `R2 >= 0.10/0.20/0.30`.
- Re-scan target vol `20%/25%/30%` and max leverage `1.2x/1.5x/2.0x`.
- The staged-entry rule lowers realized volatility, so the previous target-vol optimum may not remain optimal.

Priority 3: data-source and adjustment validation.

- Rebuild V1.1 using an adjusted or independently cross-checked ETF close source.
- Specifically investigate `159941.SZ` on 2022-07-05 and any corporate-action-like jumps.
- Do not tune further around a data artifact until this is resolved.

Priority 4: asset-pool robustness.

- Compare the six-ETF pool against no-soymeal and alternative commodity sleeve variants.
- Keep the same V1.1 rules and only change the pool, so the effect is attributable.

Lower priority or already weak:

- Top1 switch buffer was later re-scanned on recent windows; `1.05` is now the selected V1.1 default to reduce signal jitter.
- Main log-slope score overheat was not a good overheat proxy; high score usually behaved like trend strength.
- Rolling score-percentile filters cut too many profitable trend days.
