from pathlib import Path
import importlib.util

RUN = Path(__file__).resolve().parent
SOURCE = RUN.parent / "20260904_mixed_us_cn_momentum_subd_pure_momentum_core_six_etf_mixed_pool_score_min_absolute_momentum_floor" / "run_scan.py"

def main():
    spec = importlib.util.spec_from_file_location("score_floor_scan", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.subd.LOOKBACK == 25
    assert module.subd.SCORE_MIN == 0 and module.subd.SCORE_MAX == 5
    assert module.v11.ONE_WAY_COST == 0.001
    module.RUN_DIR = RUN
    module.CAPS = (0.0, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
    module.main()

if __name__ == "__main__":
    main()
