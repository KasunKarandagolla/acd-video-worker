#!/usr/bin/env python3
"""
Require match_fact_lock for current/recent real-world football briefs or artifacts.

Usage:
    python3 tools/current_event_gate_lint.py path/to/project_artifacts

The linter searches JSON/YAML/Markdown artifact text for current-event trigger terms such as latest,
most recent, 2026+, World Cup, and real match language. If found, it requires either a top-level
`match_fact_lock` object or a match_fact_lock.json/yaml file with status verified/user_confirmation_required/blocked.
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
try:
    import yaml
except ImportError:
    yaml=None

TRIGGER = re.compile(r"\b(latest|current|most recent|ongoing|202[6-9]|20[3-9]\d|World Cup|FIFA|UEFA|Copa|final|semifinal|quarterfinal|round of 16)\b", re.I)
VALID_STATUS = {'verified','user_confirmation_required','blocked','not_applicable'}


DOC_SKIP_PARTS = {'skills','analysis','implementation','shared/references','shared/contracts','provenance','archive','evals','tools'}
DOC_NAMES = {'README.md','CHANGELOG_V2_FIXES.md','CHANGELOG_V3_EDITORIAL_JOURNEY.md','CHANGELOG_V4_REPO_BRIDGE.md','CHANGELOG_V5_SAFETY_EXECUTION_PATCHES.md','CHANGELOG_V6_RUNTIME_GUARDRAILS.md','validation_report.md','ZIP_VALIDATION_REPORT.md'}

def read_texts(root: Path, include_docs=False):
    if root.is_file(): files=[root]
    else: files=[p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in {'.json','.yaml','.yml','.md','.txt'}]
    out=[]
    for p in files:
        as_posix=p.as_posix()
        if not include_docs and (p.name in DOC_NAMES or any(part in as_posix for part in DOC_SKIP_PARTS)):
            continue
        out.append((p,p.read_text(encoding='utf-8',errors='ignore')))
    return out


def find_lock(root: Path, texts):
    candidates=[]
    if root.is_dir():
        candidates += list(root.rglob('match_fact_lock.*'))
    for p,text in texts:
        if 'match_fact_lock' in text:
            candidates.append(p)
    seen=[]
    for p in candidates:
        if p in seen: continue
        seen.append(p)
        text=p.read_text(encoding='utf-8',errors='ignore') if p.exists() else ''
        if p.suffix.lower()=='.json':
            try: obj=json.loads(text)
            except Exception: obj=None
        elif p.suffix.lower() in {'.yaml','.yml'} and yaml:
            try: obj=yaml.safe_load(text)
            except Exception: obj=None
        else:
            obj=None
        if isinstance(obj,dict):
            lock=obj.get('match_fact_lock', obj)
            if isinstance(lock,dict) and str(lock.get('status')) in VALID_STATUS:
                return True, str(p), str(lock.get('status'))
        m=re.search(r"match_fact_lock:.*?status:\s*([a-zA-Z_]+)", text, re.S)
        if m and m.group(1) in VALID_STATUS:
            return True, str(p), m.group(1)
    return False, None, None


def main():
    ap=argparse.ArgumentParser(description='Require match_fact_lock when current-event trigger terms appear.')
    ap.add_argument('path', help='Project artifact file or directory')
    ap.add_argument('--include-docs', action='store_true', help='Also scan documentation/prose; noisy package audit mode')
    args=ap.parse_args()
    root=Path(args.path)
    if not root.exists(): print(f'ERROR: path not found: {root}', file=sys.stderr); return 2
    texts=read_texts(root, include_docs=args.include_docs)
    triggers=[]
    for p,text in texts:
        if TRIGGER.search(text): triggers.append(str(p))
    if not triggers:
        print('No current-event trigger terms found; match_fact_lock not required.'); return 0
    ok,path,status=find_lock(root,texts)
    if not ok:
        print('ERROR: current-event trigger terms found but no valid match_fact_lock artifact was found.')
        print('Trigger files:')
        for t in triggers[:20]: print(f'  - {t}')
        print('Required: match_fact_lock.status in {verified, user_confirmation_required, blocked, not_applicable}')
        return 1
    print(f'match_fact_lock present: {path} (status={status})')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
