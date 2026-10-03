"""Run the formal six-ETF V1.3 single-parameter LOOKBACK grid."""

import importlib.util
import sys
from pathlib import Path


RUN = Path(__file__).resolve().parent
SOURCE = RUN.parent / "20261001_lookback_5_99_step2_20260924" / "run_scan.py"
spec = importlib.util.spec_from_file_location("verified_formal_lookback_runner", SOURCE)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
module.RUN = RUN
module.VALUES = tuple(range(5, 101, 5))
# Every ETF can form even the longest 100-session score from this date.
module.ALL_SCOREABLE = module.pd.Timestamp("2020-05-07")


if __name__ == "__main__":
    module.main()
