from __future__ import annotations

import importlib.util
from pathlib import Path


RUN_DIR = Path(__file__).resolve().parent
BASE_SCAN = (
    RUN_DIR.parent
    / "20260903_mixed_us_cn_momentum_subd_pure_momentum_core_six_etf_mixed_pool_lookback"
    / "run_scan.py"
)


def main() -> None:
    spec = importlib.util.spec_from_file_location("subd_lookback_base_scan", BASE_SCAN)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load base scan module: {BASE_SCAN}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.RUN_DIR = RUN_DIR
    module.LOOKBACKS = tuple(range(25, 31))
    module.main()


if __name__ == "__main__":
    main()
