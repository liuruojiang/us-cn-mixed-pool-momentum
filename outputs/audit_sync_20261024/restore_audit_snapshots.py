"""Restore two verified audit inputs on a fresh checkout; never replace a file."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SNAPSHOTS = (('before_repair.py', '20261024_135703', 'e6934e11f76fb5b35a0b7ec61401189735710d96735d3431d9f7be1dd30af881'), ('before_parser_fix.py', '20261024_141113', 'f8953b458cad5bc3947c7d5c4833fa67394a909eb60b549dbd89da4931cfd13f'))


def main():
    results = []
    for name, directory, expected in SNAPSHOTS:
        data = (HERE / "source_snapshots" / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected, name
        target = ROOT / ".codex_backups" / directory / "poe_subd_six_etf_v1_3_bot.py"
        if not target.resolve().is_relative_to(ROOT.resolve()):
            raise RuntimeError("Audit snapshot destination leaves the checkout")
        if target.exists():
            if target.read_bytes() != data:
                raise RuntimeError(f"Preserving differing existing file: {target}")
            action = "verified existing"
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation also preserves files created during this run.
            with target.open("xb") as stream:
                stream.write(data)
            action = "restored"
        results.append({"snapshot": name, "sha256": expected, "action": action})
    print(json.dumps({"status": "PASS", "snapshots": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
