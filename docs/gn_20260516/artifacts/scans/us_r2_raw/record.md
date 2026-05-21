# US QQQ/GLD Raw Momentum R2 Threshold Scan

## Run Metadata
- run_id: 20260516_subd_us_nasdaq_gold_raw_momentum_us_qqq_gld_r2_threshold
- repo: C:\Users\Administrator.DESKTOP-95I7VVU\Desktop\动量策略\美股A股混合池子动量策略
- branch: main
- commit: d7c3790bd3a4f1b5715f4583b995542f5ad076c2
- decision: exploratory_no_change
- stability: pending_review

## Research Question
On US QQQ/GLD raw 25-day weighted-slope momentum, what happens if only an R2 threshold is added and all other V1.1 conditions remain disabled?

## Implementation Anchor
Inline Python harness using the repo's weighted log-slope formula from `research_subd_six_etf_weighted_slope.py` and Yahoo adjusted close loader from `analyze_subd_v11_us_etf_pool_20260515.py`.

## Data Snapshot
- Assets: QQQ, GLD.
- Source: Yahoo Finance chart API adjusted close.
- Load window: 2010-01-01 to 2026-05-15.
- Evaluation window starts 2015-07-13.

## Cost and Execution Assumptions
- Cost: 0.
- Slippage/open impact: 0.
- Signal: close-confirmed 25-day weighted log-slope.
- Execution semantics: next close-to-close return after the signal.
- Disabled: positive-score filter, score cap, target volatility, switch buffer, staged entry, overheat filter.

## Runtime Override Plan
No production files changed. The scan uses an inline harness and writes only this run folder.

## Commands
See `command_log.txt`.

## Output Files
- `scan_summary.csv`: long-form metrics by candidate and window.
- `window_metrics.csv`: wide comparison by candidate.
- `selection.csv`: full-window position distribution.
- `daily_curves.csv`: daily NAV/position outputs.

## Full-Sample Results
| candidate   |   R2_THRESHOLD |   ann_return |    max_dd |   sharpe_repo |   holding_day_ratio |   trades |
|:------------|---------------:|-------------:|----------:|--------------:|--------------------:|---------:|
| r2_ge_0.20  |           0.2  |     0.237082 | -0.251248 |       1.24191 |           0.0832111 |      274 |
| r2_ge_0.30  |           0.3  |     0.228351 | -0.167426 |       1.22686 |           0.140029  |      275 |
| r2_ge_0.25  |           0.25 |     0.231309 | -0.228929 |       1.22319 |           0.111437  |      277 |
| r2_ge_0.15  |           0.15 |     0.22022  | -0.279934 |       1.18256 |           0.061217  |      273 |
| r2_ge_0.35  |           0.35 |     0.214494 | -0.168391 |       1.18101 |           0.171554  |      284 |
| no_r2       |         nan    |     0.212661 | -0.328654 |       1.18055 |           0         |      116 |
| r2_ge_0.00  |           0    |     0.212661 | -0.328654 |       1.18055 |           0         |      116 |
| r2_ge_0.10  |           0.1  |     0.20908  | -0.328276 |       1.14089 |           0.039956  |      269 |

## Window Results
| candidate   |   R2_THRESHOLD |   ann_return_full |   max_dd_full |   ann_return_last_10y |   max_dd_last_10y |   ann_return_last_5y |   max_dd_last_5y |   ann_return_last_3y |   max_dd_last_3y |   ann_return_last_1y |   max_dd_last_1y |
|:------------|---------------:|------------------:|--------------:|----------------------:|------------------:|---------------------:|-----------------:|---------------------:|-----------------:|---------------------:|-----------------:|
| no_r2       |         nan    |         0.212661  |     -0.328654 |              0.206167 |         -0.328654 |             0.243459 |        -0.328654 |             0.426942 |        -0.157311 |             0.626745 |        -0.157311 |
| r2_ge_0.00  |           0    |         0.212661  |     -0.328654 |              0.206167 |         -0.328654 |             0.243459 |        -0.328654 |             0.426942 |        -0.157311 |             0.626745 |        -0.157311 |
| r2_ge_0.05  |           0.05 |         0.203211  |     -0.311944 |              0.197881 |         -0.311944 |             0.27048  |        -0.311944 |             0.413044 |        -0.165325 |             0.546779 |        -0.165325 |
| r2_ge_0.10  |           0.1  |         0.20908   |     -0.328276 |              0.20903  |         -0.328276 |             0.270346 |        -0.328276 |             0.438855 |        -0.153728 |             0.640249 |        -0.153728 |
| r2_ge_0.15  |           0.15 |         0.22022   |     -0.279934 |              0.217484 |         -0.279934 |             0.272949 |        -0.279934 |             0.368501 |        -0.17034  |             0.549111 |        -0.17034  |
| r2_ge_0.20  |           0.2  |         0.237082  |     -0.251248 |              0.23141  |         -0.251248 |             0.283486 |        -0.251248 |             0.391701 |        -0.152957 |             0.57143  |        -0.152957 |
| r2_ge_0.25  |           0.25 |         0.231309  |     -0.228929 |              0.225329 |         -0.228929 |             0.261024 |        -0.228929 |             0.36619  |        -0.172352 |             0.528385 |        -0.172352 |
| r2_ge_0.30  |           0.3  |         0.228351  |     -0.167426 |              0.229413 |         -0.167426 |             0.260695 |        -0.167426 |             0.348242 |        -0.161862 |             0.501668 |        -0.161862 |
| r2_ge_0.35  |           0.35 |         0.214494  |     -0.168391 |              0.212162 |         -0.168391 |             0.26309  |        -0.168391 |             0.32551  |        -0.168391 |             0.412364 |        -0.168391 |
| r2_ge_0.40  |           0.4  |         0.172932  |     -0.199477 |              0.176622 |         -0.199477 |             0.214498 |        -0.186558 |             0.291002 |        -0.165985 |             0.371672 |        -0.165985 |
| r2_ge_0.45  |           0.45 |         0.10715   |     -0.296413 |              0.111772 |         -0.296413 |             0.189421 |        -0.194071 |             0.282474 |        -0.138677 |             0.424792 |        -0.138677 |
| r2_ge_0.50  |           0.5  |         0.0776719 |     -0.271232 |              0.076518 |         -0.271232 |             0.153031 |        -0.226134 |             0.246849 |        -0.138677 |             0.4199   |        -0.138677 |

## Stability Classification
Pending review. Full-sample optimum is around 0.20-0.30, but recent-window robustness needs user review before any default proposal.

## Decision
Exploratory no-change. Do not promote a threshold yet.

## User-Facing Summary
R2 around 0.20 gives the best full-window Sharpe and return; 0.30 gives much lower drawdown but slightly lower return. Very high thresholds over-filter and spend too much time in cash.
