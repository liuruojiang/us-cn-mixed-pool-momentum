"""Capture the formal V1.3 historical loader's latest complete daily input.

No signals, orders, or performance are calculated here. The exchange holiday
notice makes 2026-09-24 the last completed session as of 2026-09-26.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
BOT = ROOT / "poe_subd_six_etf_v1_3_bot.py"
CUTOFF = pd.Timestamp("2026-09-24")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location("six_etf_v13_formal", BOT)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load formal V1.3 entrypoint")
    bot = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = bot
    spec.loader.exec_module(bot)
    config = bot._build_config(end_date=CUTOFF)
    raw, sources = bot.load_close(config)
    raw = raw.loc[raw.index >= config.start_date].copy()
    codes = list(bot.ASSETS)
    last_by_asset = {
        code: str(pd.Timestamp(raw[code].dropna().index.max()).date())
        if raw[code].notna().any() else None
        for code in codes
    }
    if not raw.index.is_unique or not raw.index.is_monotonic_increasing:
        raise RuntimeError("Formal loader returned duplicate or unsorted dates")
    if raw.index.max() != CUTOFF or any(day != str(CUTOFF.date()) for day in last_by_asset.values()):
        raise RuntimeError(f"Incomplete latest session: last_by_asset={last_by_asset}")
    if set(raw.columns) != set(codes):
        raise RuntimeError(f"Unexpected columns: {list(raw.columns)}")

    raw_path = OUT / "prices_raw_qfq_through_20260924.csv.gz"
    sources_path = OUT / "sources_formal_loader.csv"
    raw.rename_axis("date").to_csv(raw_path, compression="gzip", float_format="%.15g")
    sources.to_csv(sources_path, index=False)

    # Keep the repository's existing calendar cache untouched while running the
    # exact official alignment and date-quality checks on a copied cache.
    old_cache = ROOT / bot.TRADING_CALENDAR_CACHE_PATH
    new_cache = OUT / "calendar_cache_for_audit.csv"
    if old_cache.exists() and not new_cache.exists():
        shutil.copy2(old_cache, new_cache)
    bot.TRADING_CALENDAR_CACHE_PATH = new_cache
    aligned, common_last, actual_last = bot.align_prices_to_common_valid_date(raw, codes)
    flags = bot._price_forward_fill_flags(raw, aligned, codes)
    aligned_path = OUT / "prices_aligned_qfq_through_20260924.csv.gz"
    flags_path = OUT / "price_ffill_flags_through_20260924.csv.gz"
    aligned.rename_axis("date").to_csv(aligned_path, compression="gzip", float_format="%.15g")
    flags.rename_axis("date").to_csv(flags_path, compression="gzip")

    manifest = {
        "status": "candidate_pending_independent_L1_audit",
        "captured_at_asia_shanghai": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "cutoff": str(CUTOFF.date()),
        "calendar_authority": "SSE/SZSE 2026-09-17 holiday notices; 09-25 through 09-27 closed",
        "entrypoint": str(BOT),
        "entrypoint_sha256": sha256(BOT),
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "config": {"source": config.source, "start_date": str(config.start_date.date()), "end_date": str(config.end_date.date())},
        "raw": {"path": str(raw_path), "sha256": sha256(raw_path), "rows": len(raw), "start": str(raw.index.min().date()), "end": str(raw.index.max().date()), "last_by_asset": last_by_asset},
        "aligned": {"path": str(aligned_path), "sha256": sha256(aligned_path), "rows": len(aligned), "start": str(aligned.index.min().date()), "end": str(common_last.date()), "last_by_asset": {k: str(v.date()) for k, v in actual_last.items()}},
        "flags": {"path": str(flags_path), "sha256": sha256(flags_path), "count_by_asset": {code: int(flags[code].sum()) for code in codes}},
        "sources": {"path": str(sources_path), "sha256": sha256(sources_path)},
        "calendar_cache_for_audit": {"path": str(new_cache), "sha256": sha256(new_cache) if new_cache.exists() else None},
        "limitation": "No signals, account or performance checked; provider supplied qfq labels require independent L1 verification",
    }
    (OUT / "capture_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"raw_rows": len(raw), "aligned_rows": len(aligned), "common_last": str(common_last.date()), "last_by_asset": last_by_asset, "sources": sources.to_dict(orient="records")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
