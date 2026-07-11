#!/usr/bin/env python3
"""Probe a local OpenMontage checkout for artifact schemas before writing real edit_decisions.

Usage:
    python3 tools/openmontage_schema_probe.py /home/kasun/Music/Director/OpenMontage
    python3 tools/openmontage_schema_probe.py --json /path/to/OpenMontage

The probe also reports the git remote so the user can see whether the checkout matches the locked
`calesthio/OpenMontage` target or a different fork.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

EXPECTED = ['edit_decisions','asset_manifest','scene_plan','render_report','script']
TARGET_REMOTE = 'calesthio/OpenMontage'


def run(cmd, cwd):
    try:
        return subprocess.check_output(cmd, cwd=cwd, stderr=subprocess.STDOUT, text=True).strip()
    except Exception as exc:
        return f'error: {exc}'


def main():
    ap=argparse.ArgumentParser(description='Probe OpenMontage artifact schemas and fork alignment.')
    ap.add_argument('openmontage_root', nargs='?', default='/home/kasun/Music/Director/OpenMontage')
    ap.add_argument('--json', action='store_true', help='Emit JSON only (default behavior also JSON; retained for clarity)')
    args=ap.parse_args()
    root=Path(args.openmontage_root).expanduser().resolve()
    schema_dir=root/'schemas'/'artifacts'
    found=[]
    for name in EXPECTED:
        matches=list(schema_dir.glob(f'{name}*')) if schema_dir.exists() else []
        if matches:
            found.append({'name':name,'paths':[str(p) for p in matches]})
    missing=[n for n in EXPECTED if n not in {f['name'] for f in found}]
    status='passed' if not missing else ('degraded' if found else 'blocked')
    remote=run(['git','remote','get-url','origin'], root) if (root/'.git').exists() else 'not_a_git_checkout_or_missing'
    head=run(['git','rev-parse','HEAD'], root) if (root/'.git').exists() else 'unknown'
    fork_alignment='matches_target' if TARGET_REMOTE.lower() in remote.lower() else ('unknown' if remote.startswith('error') or remote.startswith('not_') else 'different_remote')
    result={'openmontage_schema_lock': {
        'openmontage_root': str(root),
        'git_remote_origin': remote,
        'git_head': head,
        'target_remote_hint': TARGET_REMOTE,
        'fork_alignment': fork_alignment,
        'schemas_path': str(schema_dir),
        'schemas_found': found,
        'missing_schemas': missing,
        'mapped_fields': [],
        'unmapped_fields': [],
        'forbidden_assumptions': ['Do not write real edit_decisions until required schemas are found and mapped'],
        'bridge_status': status
    }}
    print(json.dumps(result, indent=2))
    return 0 if status == 'passed' else 1

if __name__=='__main__':
    raise SystemExit(main())
