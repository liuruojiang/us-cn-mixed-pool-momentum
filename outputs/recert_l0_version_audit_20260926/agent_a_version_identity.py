"""L0-only identity gate. Reads source text; never imports or runs a backtest."""

import argparse
import ast
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_ASSETS = {
    "159915.SZ", "159941.SZ", "513030.SH", "513520.SH",
    "159985.SZ", "518880.SH",
}
EXPECTED_CONSTANTS = {
    "VERSION": "1.3",
    "LOOKBACK": 25,
    "SCORE_MIN": 0.5,
    "SCORE_MAX": 5.5,
    "R2_THRESHOLD": 0.25,
    "SWITCH_BUFFER": 1.0,
    "INITIAL_ENTRY_FRACTION": 1.0,
    "DEFAULT_MAX_LEV": 1.0,
    "ONE_WAY_COST": 0.001,
    "CASH_ANNUAL_YIELD": 0.0,
    "TARGET_VOL_ENABLED": False,
    "OVERHEAT_ENABLED": False,
    "STAGED_ENTRY_ENABLED": False,
}
EXPECTED_SOURCE_SHA256 = "21a5867f51367d215a6f9913dafae1a462bf2316f7c59e7a860d43448c63ee72"
EXPECTED_DATA_SHA256 = "0cc4af45158d6aaab4594b869b79309a96e8e3cc2f21a0205c38128913bec2aa"
DATA_PATH = ROOT / "quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer/price_snapshot_qfq.csv.gz"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_source(path, *, injected_score_max=None, require_hash=True):
    errors = []
    source = path.read_text(encoding="utf-8-sig")
    tree = ast.parse(source, filename=str(path))
    constants = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in (*EXPECTED_CONSTANTS, "ASSETS"):
                    try:
                        constants[target.id] = ast.literal_eval(node.value)
                    except ValueError:
                        errors.append(f"{target.id}: not a literal")
    if injected_score_max is not None:
        constants["SCORE_MAX"] = injected_score_max
    for key, expected in EXPECTED_CONSTANTS.items():
        actual = constants.get(key, "<missing>")
        if type(actual) is not type(expected) or actual != expected:
            errors.append(f"{key}: got {actual!r}, expected {expected!r}")
    actual_assets = constants.get("ASSETS", {})
    if set(actual_assets) != EXPECTED_ASSETS:
        errors.append(f"ASSETS: got {sorted(actual_assets)}, expected {sorted(EXPECTED_ASSETS)}")
    if require_hash and sha256(path) != EXPECTED_SOURCE_SHA256:
        errors.append("source SHA256 differs from frozen V1.3 acceptance")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    formal = ROOT / "poe_subd_six_etf_v1_3_bot.py"
    mixed = ROOT / "poe_subd_mixed_pool_v1_3_bot.py"
    if args.self_test:
        good = check_source(formal)
        wrong_family = check_source(mixed)
        wrong_cap = check_source(formal, injected_score_max=5.0, require_hash=False)
        data_ok = sha256(DATA_PATH) == EXPECTED_DATA_SHA256
        print(f"formal: {'ACCEPT' if not good else 'REJECT'} {good}")
        print(f"mixed-pool V1.3: {'REJECT' if wrong_family else 'ACCEPT'} {wrong_family}")
        print(f"in-memory stale Score cap 5: {'REJECT' if wrong_cap else 'ACCEPT'} {wrong_cap}")
        print(f"frozen data SHA256: {'MATCH' if data_ok else 'MISMATCH'}")
        if good or not wrong_family or not wrong_cap or not data_ok:
            raise SystemExit(1)
        return
    errors = check_source(formal)
    if sha256(DATA_PATH) != EXPECTED_DATA_SHA256:
        errors.append("data SHA256 differs from frozen V1.3 acceptance")
    print("ACCEPT" if not errors else "REJECT", errors)
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
