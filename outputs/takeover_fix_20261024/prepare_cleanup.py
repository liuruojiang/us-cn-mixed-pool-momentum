"""Freeze only new disposable scratch files; do not execute deletion here."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'outputs/takeover_fix_20261024'
targets = [ROOT/'outputs'/family/suffix
           for family in ('takeover_audit_20261024','takeover_fix_20261024')
           for suffix in ('scratch','data/scratch')]
old = json.loads((ROOT/'outputs/audit_sync_20261024/cleanup_record.json').read_text(encoding='utf-8'))
blocked = [Path(p).resolve() for p in old['targets']] + [(ROOT/p).resolve() for p in old['previously_blocked']]
tracked = set(subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode('utf-8').split('\0'))
entries = []
for directory in targets:
    assert directory.resolve() == directory and directory.is_relative_to(ROOT)
    assert not any(directory==b or directory.is_relative_to(b) or b.is_relative_to(directory) for b in blocked)
    if not directory.exists():
        continue
    files, links = [], []
    for p in sorted(directory.rglob('*')):
        if p.is_symlink() or p.is_junction():
            to=p.resolve(strict=True)
            assert to.is_relative_to(directory) and to.is_dir(),p
            links.append({'path':p.relative_to(ROOT).as_posix(),'target':to.relative_to(ROOT).as_posix()})
        elif p.is_file():
            rel=p.relative_to(ROOT).as_posix()
            assert rel not in tracked,rel
            files.append({'path':rel,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size})
    entries.append({'directory':directory.relative_to(ROOT).as_posix(),'files':files,'links':links})
plan={'workspace':str(ROOT),'targets':entries,'previously_blocked_excluded':[str(p) for p in blocked],
      'file_count':sum(len(x['files']) for x in entries),'directory_link_count':sum(len(x['links']) for x in entries),
      'bytes':sum(f['bytes'] for x in entries for f in x['files']),
      'execution':'After verified commit/push only; no old blocked targets; backup and hash verification required.'}
(OUT/'cleanup_plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
template=(ROOT/'cleanup_takeover_tests_20261024.bat').read_text(encoding='utf-8')
start=template.index("    $plan = ConvertFrom-Json @'\n")+len("    $plan = ConvertFrom-Json @'\n")
end=template.index("\n'@",start)
text=template[:start]+json.dumps(plan,ensure_ascii=False,indent=2)+template[end:]
batch=ROOT/'cleanup_after_fix_20261024.bat'
assert not batch.exists(),'Preserve the existing batch and its frozen scope'
batch.write_bytes(text.replace('\r\n','\n').replace('\n','\r\n').encode('utf-8'))
print(json.dumps({k:v for k,v in plan.items() if k not in ('targets','previously_blocked_excluded')},ensure_ascii=False))
