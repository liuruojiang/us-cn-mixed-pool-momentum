# EWJ Clipped From 2019-06-25 Test

- Test rule: EWJ price history before 2019-06-25 is hidden from the V1.3 pool, so it can only score after the normal 28-day lookback is available.
- Baseline: QQQ + GLD + CN_CYB_399006, same end date 2026-06-17.

| Case | Data first | First score | First held | Held days | Held compound | Full ann. | Delta full ann. | Since 2019-06-25 ann. | Delta since join | Pool effect |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| EWJ clipped | 2019-06-25 | 2019-08-01 | 2019-09-23 | 247 | -5.51% | 16.53% | -0.50% | 18.80% | -1.44% | negative / negative |
| Baseline same end | n/a | n/a | n/a | n/a | n/a | 17.04% | n/a | 20.24% | n/a | n/a |

## Reference: A-share Nikkei Diagnostic
| Code | Data first | Held days | Held compound | Full ann. | Delta ann. | Pool effect |
|---|---:|---:|---:|---:|---:|---:|
| 513520.SH | 2019-06-25 | 281 | 18.93% | 18.48% | 1.44% | positive |

## Conclusion
- EWJ clipped to the same 2019-06-25 availability is `negative` on full-period annualized delta and `negative` on post-2019-06-25 annualized delta.
- EWJ's own held segment is negative (-5.51%).
