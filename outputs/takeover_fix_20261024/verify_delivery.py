"""Verify frozen repair acceptance and produce a byte-exact evidence manifest."""
from pathlib import Path
import ast
import hashlib
import json
import re
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
SOURCE_SHA = 'daf96cf4b39ab2919c9e8b7d82e74f96177748a1f4c5a6be2da7b5637e4965ca'
BEFORE_SHA = '8354e9c4b835c77f11809d5d0b727f54e75e7f7bc5a1fc5aa282ccb73bfd1f57'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def junit(path):
    nodes = list(ET.parse(path).getroot().iter('testcase'))
    keys = [(t.get('classname'), t.get('name')) for t in nodes]
    assert len(keys) == len(set(keys)), path
    errors = sum(t.find('error') is not None for t in nodes)
    failed = sum(t.find('failure') is not None for t in nodes)
    skipped = sum(t.find('skipped') is not None for t in nodes)
    return {'tests': len(nodes), 'passed': len(nodes)-errors-failed-skipped,
            'failed': failed, 'errors': errors, 'skipped': skipped}


assert sha(ROOT / 'poe_subd_six_etf_v1_3_bot.py') == SOURCE_SHA
assert sha(OUT / 'source_snapshots/before_fix.py') == BEFORE_SHA
full = junit(OUT / 'full_suite.xml')
assert full == dict(tests=798, passed=797, failed=0, errors=0, skipped=1), full
for name, count in [('targeted.xml', 82), ('portable_data.xml', 10), ('isolated_tests.xml', 57)]:
    result = junit(OUT / name)
    assert result == dict(tests=count, passed=count, failed=0, errors=0, skipped=0), (name,result)
before = junit(ROOT / 'outputs/takeover_audit_20261024/adversarial.xml')
assert before == dict(tests=32, passed=25, failed=7, errors=0, skipped=0)

for path in [OUT / 'math/result.json', OUT / 'isolated_math_result.json']:
    math = read(path)
    assert math['status'] == 'PASS' and math['code_sha256'] == SOURCE_SHA
    assert math['pre_repair_code_sha256'] == BEFORE_SHA
    parity = math['all_column_exact_baseline_parity']
    assert parity['passed'] and parity['rows'] == 3597 and parity['columns'] == 105
    assert math['changed_ast_functions'] == ['_recover_calendar_price_conflict', 'parse_all_date_ranges']
    assert math['cost_monotonicity'] and len(math['prefix_checks']) == 7
    assert all(row['passed'] for row in math['prefix_checks']) and len(math['metrics']) == 5

archive = read(ROOT / 'outputs/takeover_audit_20261024/evidence_manifest.json')
for name, expected in archive['retained_evidence_files'].items():
    path = ROOT / name
    if name == 'tests/test_v13_takeover_reporting_20261024.py':
        path = OUT / 'source_snapshots/before_reporting_output_isolation.py'
    assert sha(path) == expected, name
tests = list(ROOT.glob('tests/test_v13_takeover*_20261024.py'))
assert len(tests) == 5
for path in tests + [ROOT/'poe_subd_six_etf_v1_3_bot.py']:
    ast.parse(path.read_text(encoding='utf-8'), filename=str(path))

doc = ROOT / 'docs/subd_six_etf_v1_3_takeover_fix_20261024.md'
for target in re.findall(r'\]\(([^)]+)\)', doc.read_text(encoding='utf-8')):
    if '://' not in target:
        linked = (doc.parent / target.split('#')[0]).resolve()
        if linked != OUT/'delivery_verification.json':
            assert linked.exists(), target

result = {'status':'PASS', 'source_sha256':SOURCE_SHA, 'before_sha256':BEFORE_SHA,
          'full_suite':full, 'prior_adversarial':before, 'previous_seven_failures_repaired':True,
          'additional_boundary_tests':25, 'isolated_index_export_tests':57,
          'isolated_math_exact_parity':{'rows':3597,'columns':105},
          'old_evidence_entries_verified':len(archive['retained_evidence_files']),
          'data_cutoff':'2026-09-30', 'hosted_deployment':False, 'orders':False,
          'cleanup_status':'See cleanup_result.json when created; Git cleanliness is separate.'}
(OUT/'delivery_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
files = [p for p in OUT.rglob('*') if p.is_file() and 'scratch' not in p.relative_to(OUT).parts
         and p.name != 'evidence_manifest.json']
files += tests + [ROOT/'poe_subd_six_etf_v1_3_bot.py', ROOT/'README.md', ROOT/'TASK_STATE.md', doc]
(OUT/'evidence_manifest.json').write_text(json.dumps({'source_sha256':SOURCE_SHA,
    'files':{p.relative_to(ROOT).as_posix():sha(p) for p in sorted(files)}},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
