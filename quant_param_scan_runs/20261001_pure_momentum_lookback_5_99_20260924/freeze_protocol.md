# Pure-momentum LOOKBACK sweep, frozen before results

- Object: six China-listed ETF V1.3 source engine `poe_subd_six_etf_v1_3_bot.py`, research-only runtime overrides; no source or production change.
- Grid: 5, 7, ..., 99 trading days (48 values). Step 2 from 5 cannot include 100. Include 25 as the pure-momentum reference.
- Pure-momentum definition: same weighted log-price slope Score (`p=1`, annualization 252), strict `Score > 0`, no Score upper cap (`SCORE_MAX=+inf`), no R² gate (`r2_threshold=None`), no switch Buffer (`1.00`), Top1 full entry or cash when no positive Score. Target-vol, overheat and staged entry remain disabled as in V1.3.
- The positive Score rule is the directional momentum rule. This is distinct from the historical `0<Score<5` capped base and from the V1.3 `0.5<Score<5.5, R²>=0.25` formal version.
- Data: reuse L1 verified Tencent-labelled qfq aligned six-ETF close panel and fill flags, 2011-12-09 to 2026-09-24, 3,594 China ETF sessions. Do not refresh or splice data. Report the six-ETF all-scoreable period from 2020-01-09 separately because Full dynamically adds ETFs after listing.
- Costs/account: one ETF or cash, no borrow, max exposure 1, zero cash yield, 0.10% combined one-way fee/slippage per buy and sell leg. Old holding earns T-close-to-T-close return, T-close signal hypothetically fills at that same close. This is a paper model, without verified executable fills, premiums, impact or capacity.
- Windows: Full, trailing 2520/1260/756/252 sessions, and 2020-01-09 common-scoreable window. Annualize using N-1 NAV changes. Show annualized net return and max drawdown for all five mandatory windows for every candidate.
- Baseline gate: the unchanged formal 25-day path must match saved L2 daily positions, turnover, costs and NAV before any pure result is accepted. Recompute every exported candidate-window annual return and drawdown from its daily NAV independently.
- Decision: characterize the retrospective shape and compare with the pure 25-day reference. No ex-post winner promotion; formal V1.3 and Poe remain unchanged. Any source, price, cost or execution-timing change requires a new run.
