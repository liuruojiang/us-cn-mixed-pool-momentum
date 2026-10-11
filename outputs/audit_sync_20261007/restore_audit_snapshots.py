"""Restore two verified audit inputs on a fresh checkout; never replace a file."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SNAPSHOTS = (
    ("before_first_audit.py", "20261007_163920", "b49c86944f0ef843f0eb23eebe396122fee0db5a90c6250789f21b3d110df988"),
    ("before_doublecheck.py", "20261007_200248", "7a4cf15ff1603764dbf3469aab9b85f33756c98129116b4ce7dedb46eb48e1e3"),
)


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
