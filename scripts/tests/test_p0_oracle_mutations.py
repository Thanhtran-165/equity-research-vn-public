#!/usr/bin/env python3
"""Negative mutations cho REQ-040/REQ-075 trên một fixture 75/75.

Chuẩn bị fixture trước:
  python3 scripts/build_report.py TJC industrial
Chạy:
  python3 scripts/tests/test_p0_oracle_mutations.py --fixture /tmp/vn100_TJC
"""
import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERIFIER = Path(os.environ.get('EQUITY_VERIFIER', ROOT / 'scripts/independent_verifier.py'))


def atomic_json(path, value):
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    os.replace(tmp, path)


def run_verify(work, ticker):
    report = work / f'{ticker}_Complete_Report.html'
    r = subprocess.run(
        ['python3', str(VERIFIER), ticker, str(report)], cwd=work,
        capture_output=True, text=True, timeout=300,
    )
    statuses = {}
    for req in ('REQ-040', 'REQ-075'):
        p = work / '.task-state/evidence' / f'{req}.json'
        statuses[req] = json.load(open(p)).get('status') if p.exists() else 'missing'
    return r.returncode, statuses


def mutate_sidecar_source_none(work):
    path = work / 'preflight-sector.json'
    data = json.load(open(path))
    data['source'] = 'none'
    atomic_json(path, data)


def mutate_sidecar_missing(work):
    os.replace(work / 'preflight-sector.json', work / 'preflight-sector.json.removed')


def mutate_sidecar_sha_missing(work):
    path = work / 'preflight-sector.json'
    data = json.load(open(path))
    data.pop('source_sha256', None)
    atomic_json(path, data)


def mutate_phase1_periods_missing(work):
    path = work / '.task-state/task-state.json'
    data = json.load(open(path))
    data['phases']['phase1_data']['result'].pop('periods', None)
    atomic_json(path, data)


def mutate_sponsor_ok_not_bool(work):
    path = work / '.task-state/task-state.json'
    data = json.load(open(path))
    data['phases']['phase0_sponsor']['result']['sponsor_ok'] = None
    atomic_json(path, data)


def mutate_cashflow_csv_missing(work):
    path = work / 'source-pack/cash_flow_sponsor.csv'
    os.replace(path, path.with_suffix('.csv.removed'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fixture', default='/tmp/vn100_TJC')
    ap.add_argument('--ticker', default='TJC')
    args = ap.parse_args()
    fixture = Path(args.fixture)
    if not (fixture / f'{args.ticker}_Complete_Report.html').exists():
        print(f'SKIP integration mutation: thiếu fixture {fixture}')
        return 0

    root = Path(tempfile.mkdtemp(prefix='p0_oracle_mutations_'))
    try:
        baseline = root / 'baseline'
        shutil.copytree(fixture, baseline)
        rc, statuses = run_verify(baseline, args.ticker)
        if rc != 0 or statuses != {'REQ-040': 'pass', 'REQ-075': 'pass'}:
            raise AssertionError(f'fixture không phải baseline 75/75: rc={rc}, {statuses}')

        cases = [
            ('sidecar_source_none', mutate_sidecar_source_none, 'REQ-040'),
            ('sidecar_missing', mutate_sidecar_missing, 'REQ-040'),
            ('sidecar_sha_missing', mutate_sidecar_sha_missing, 'REQ-040'),
            ('phase1_periods_missing', mutate_phase1_periods_missing, 'REQ-075'),
            ('sponsor_ok_not_bool', mutate_sponsor_ok_not_bool, 'REQ-075'),
            ('cashflow_csv_missing', mutate_cashflow_csv_missing, 'REQ-075'),
        ]
        for name, mutate, expected_req in cases:
            work = root / name
            shutil.copytree(fixture, work)
            mutate(work)
            rc, statuses = run_verify(work, args.ticker)
            if rc == 0 or statuses.get(expected_req) != 'fail':
                raise AssertionError(f'{name} lọt: rc={rc}, {statuses}')
            print(f'PASS mutation {name}: {expected_req} FAIL, exit={rc}')
        print(f'OK {len(cases)}/{len(cases)} negative mutations')
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == '__main__':
    main()
