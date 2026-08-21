# Candidate Join Timing Audit

- `data_first_available`: raw source first usable close.
- `first_score_date`: after V1.3 lookback/calendar alignment, the first date the asset has a calculable score.
- `first_actual_held_date`: first date it actually contributes to strategy return as prior-day holding.

## Positive Pool-Effect Candidates
| Code | Data first | First score | First held | Held days | Held compound | Delta ann. | Full ann. | Source note |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| KMLM | 2020-12-02 | 2021-01-11 | 2021-01-12 | 260 | 28.23% | 2.25% | 19.53% | total-return/adjusted-close |
| 159985.SZ | 2019-12-05 | 2020-01-14 | 2020-03-16 | 325 | 40.53% | 2.09% | 19.12% | sina_raw_unadjusted_no_detected_split_patch |
| BTC-USD | 2014-09-17 | 2014-10-31 | 2014-11-20 | 503 | 82.83% | 1.88% | 19.16% | total-return/adjusted-close |
| 518880.SH | 2013-07-29 | 2013-09-04 | 2014-03-04 | 394 | 23.24% | 1.62% | 18.66% | sina_raw_unadjusted_no_detected_split_patch |
| 513520.SH | 2019-06-25 | 2019-08-01 | 2019-09-25 | 281 | 18.93% | 1.44% | 18.48% | sina_raw_unadjusted_no_detected_split_patch |
| DBMF | 2019-05-08 | 2019-06-17 | 2019-08-30 | 226 | -0.35% | 0.76% | 18.04% | total-return/adjusted-close |
| 159941.SZ | 2015-07-13 | 2015-08-19 | 2015-09-24 | 620 | 63.79% | 0.61% | 17.64% | sina_raw_split_continuity_159941_pre_20220705_x0.25 |
| SPY | 2006-10-13 | 2007-02-12 | 2007-04-03 | 577 | 17.24% | 0.36% | 17.65% | total-return/adjusted-close |
| DBC | 2006-10-13 | 2007-02-12 | 2007-02-28 | 869 | 39.04% | 0.22% | 17.51% | total-return/adjusted-close |

## Japan ETF Check
| Code | Meaning | Data first | First score | First held | Held days | Held compound | Pool effect | Delta ann. | Full ann. | Full MDD |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| EWJ | US-listed Japan ETF | 2006-10-13 | 2007-02-12 | 2007-03-05 | 693 | -13.84% | negative | -2.95% | 14.33% | -27.18% |
| 513520.SH | A-share Nikkei ETF diagnostic | 2019-06-25 | 2019-08-01 | 2019-09-25 | 281 | 18.93% | positive | 1.44% | 18.48% | -25.20% |

## Interpretation
- `513520.SH` only starts from 2019-06-25 in this diagnostic source, first scores on 2019-08-01, and first actually affects returns on 2019-09-25.
- `EWJ` has data from 2006-10-13 and can score from 2007-02-12, but under this V1.3 pool test it is negative both when held and as a pool addition.
- So your memory is consistent for the US Japan ETF: the US-listed Japan leg (`EWJ`) is a negative addition here; the positive result belongs to the shorter-history A-share Nikkei ETF diagnostic (`513520.SH`).
