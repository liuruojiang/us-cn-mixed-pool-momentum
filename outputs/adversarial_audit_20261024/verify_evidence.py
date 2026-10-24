"""Verify audit evidence and write a manifest, without editing production files."""
from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
EXPECTED = 'e6934e11f76fb5b35a0b7ec61401189735710d96735d3431d9f7be1dd30af881'
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
assert sha(ROOT / 'poe_subd_six_etf_v1_3_bot.py') == EXPECTED
suite = ET.parse(OUT / 'baseline.xml').getroot().find('testsuite')
assert int(suite.attrib['tests']) == 691
assert int(suite.attrib['failures']) == 0 and int(suite.attrib['errors']) == 0
assert int(suite.attrib['skipped']) == 1
weekend = json.loads((OUT / 'weekend_results.json').read_text(encoding='utf-8'))
assert len(weekend['cases']) == 6
assert sum(c['status']['signal_valid'] != c['should_be_valid'] for c in weekend['cases']) == 3
assert all(c['diagnostic_candidate_status']['signal_valid'] == c['should_be_valid'] for c in weekend['cases'])
data = json.loads((OUT / 'data/calendar_cache_result.json').read_text(encoding='utf-8'))
assert data['initial_http_calls'] == data['http_calls_after_recovery']
assert data['after_cache_invalidation']['status'] == 'accepted'
assert len(data['non_session_negative_controls']) == 2
report = json.loads((OUT / 'reporting/reporting_results.json').read_text(encoding='utf-8'))
assert report['fault_injection'][1]['report_claims_valid_no_trade']
assert report['multi_window']['expected_records'] == 65
assert report['multi_window']['actual_records'] == 35
math = json.loads((OUT / 'math/result.json').read_text(encoding='utf-8'))
assert math['status'] == 'PASS' and math['rows'] == 3597
assert len(math['prefix_checks']) == 7
files = {}
excluded = {'evidence_manifest.json', '2026-09-26_2026-09-24_signal.txt',
            '2026-09-26_2026-09-25_signal.txt', '2026-09-27_2026-09-24_signal.txt'}
for path in sorted(OUT.rglob('*')):
    if path.is_file() and path.name not in excluded and 'pytest_tmp' not in path.parts and '__pycache__' not in path.parts:
        files[path.relative_to(OUT).as_posix()] = sha(path)
manifest = {'status': 'verified', 'production_sha256': EXPECTED,
            'confirmed_findings': 4, 'severity': 'P2', 'existing_regressions_passed': 690,
            'existing_regressions_skipped': 1, 'files': files,
            'cleanup': 'blocked by policy; temporary paths retained as documented in report.md'}
(OUT / 'evidence_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'status': 'verified', 'files': len(files), 'production_unchanged': True,
                  'confirmed_findings': 4, 'existing_passed': 690}))
