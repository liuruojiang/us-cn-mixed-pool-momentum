"""Verify final code, independent audits, unchanged first-audit evidence and links."""
from pathlib import Path
import hashlib
import json
import re
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
FINAL_SHA = '8354e9c4b835c77f11809d5d0b727f54e75e7f7bc5a1fc5aa282ccb73bfd1f57'
ORIGINAL_SHA = 'e6934e11f76fb5b35a0b7ec61401189735710d96735d3431d9f7be1dd30af881'
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):
    return json.loads(path.read_text(encoding='utf-8'))
def junit(path):
    nodes = list(ET.parse(path).getroot().iter('testcase'))
    keys = [(x.get('classname'), x.get('name')) for x in nodes]
    assert len(keys) == len(set(keys)), f'Duplicate tests in {path}'
    return {'tests': len(nodes),
            'failed': sum(x.find('failure') is not None for x in nodes),
            'errors': sum(x.find('error') is not None for x in nodes),
            'skipped': sum(x.find('skipped') is not None for x in nodes)}

assert sha(ROOT / 'poe_subd_six_etf_v1_3_bot.py') == FINAL_SHA
backup = ROOT / '.codex_backups/20261024_135703/poe_subd_six_etf_v1_3_bot.py'
assert sha(backup) == ORIGINAL_SHA
full = junit(OUT / 'verified_final_suite.xml')
assert full == {'tests': 741, 'failed': 0, 'errors': 0, 'skipped': 1}, full
before = junit(OUT / 'before_final_tests.xml')
assert before == {'tests': 21, 'failed': 13, 'errors': 0, 'skipped': 0}, before
data = junit(OUT / 'data/independent_final.xml')
reporting = junit(OUT / 'reporting/final_pytest.xml')
assert data == {'tests': 10, 'failed': 0, 'errors': 0, 'skipped': 0}, data
assert reporting == {'tests': 19, 'failed': 0, 'errors': 0, 'skipped': 0}, reporting
math_dir = OUT / 'math/final_8354e9c4'
math = read(math_dir / 'result.json')
assert math['status'] == 'PASS' and math['code_sha256'] == FINAL_SHA
parity = math['all_column_exact_baseline_parity']
assert parity['passed'] and parity['rows'] == 3597 and parity['columns'] == 105
assert math['cost_monotonicity'] and len(math['prefix_checks']) == 7
assert all(x['passed'] for x in math['prefix_checks'])
assert len(math['metrics']) == 5
mixed = read(OUT / 'reporting/mixed_conjunction_result.json')
assert mixed['code_sha256'] == FINAL_SHA
assert mixed['actual'] == mixed['expected'] and sum(mixed['actual'].values()) == 100
old_dir = ROOT / 'outputs/adversarial_audit_20261024'
old = read(old_dir / 'evidence_manifest.json')
for name, expected in old['files'].items():
    assert sha(old_dir / name) == expected, f'First-audit evidence changed: {name}'

doc = ROOT / 'docs/subd_six_etf_v1_3_repair_audit_20261024.md'
result = {'status': 'PASS', 'final_source_sha256': FINAL_SHA,
          'original_source_sha256': ORIGINAL_SHA, 'full_suite': full,
          'unique_tests_passed': full['tests'] - full['skipped'],
          'repair_before': before, 'independent_data': data, 'independent_reporting': reporting,
          'all_column_parity': {'rows': 3597, 'columns': 105, 'exact': True},
          'old_audit_files_unchanged': len(old['files']),
          'mixed_three_year_trade_records': 100,
          'deployment': 'source and evidence synchronization recorded separately; no hosted deployment or orders',
          'data_cutoff': '2026-09-30; frozen replay, not current market performance'}
(OUT / 'delivery_verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
# Check actual relative Markdown links after materializing the verification record.
for target in re.findall(r'\]\(([^)]+)\)', doc.read_text(encoding='utf-8')):
    if '://' not in target:
        assert (doc.parent / target.split('#')[0]).resolve().exists(), target
paths = [ROOT / name for name in [
    'poe_subd_six_etf_v1_3_bot.py', 'README.md',
    'docs/subd_six_etf_v1_3_20260904.md', 'docs/subd_six_etf_v1_3_repair_audit_20261024.md',
    'tests/test_poe_subd_external_review_regressions.py', 'tests/test_v13_repair_20261024.py',
    'tests/test_v13_postfix_data_20261024.py', 'tests/test_v13_postfix_reporting_20261024.py']]
paths += [p for p in OUT.rglob('*') if p.is_file() and p.name != 'evidence_manifest.json'
          and '__pycache__' not in p.parts and not any(part.endswith('_tmp') for part in p.parts)]
manifest = {'code_sha256': FINAL_SHA,
            'files': {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(set(paths))}}
(OUT / 'evidence_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
