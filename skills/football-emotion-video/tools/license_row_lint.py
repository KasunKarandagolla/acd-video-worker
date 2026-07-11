#!/usr/bin/env python3
"""
Lint music_sfx_candidate JSON rows before license review.

Usage:
    python3 tools/license_row_lint.py path/to/candidates.json
    cat candidates.json | python3 tools/license_row_lint.py -

Input must be one JSON object or a JSON array of music_sfx_candidate objects. This linter does not
approve licenses; it only checks that rows are complete enough for human/license-checker review.
"""
import argparse
import json
import re
import sys

SEARCH_PAGE_PATTERNS=[r"/search[/?]",r"[?&]q=",r"[?&]search=",r"/category/",r"/tag/",r"/tags/",r"/browse/"]

def looks_like_search_page(url: str) -> bool:
    if not url: return True
    return any(re.search(pat,url,re.I) for pat in SEARCH_PAGE_PATTERNS)

def lint_one(entry):
    asset_id=entry.get('asset_id','<unknown>') if isinstance(entry,dict) else '<invalid>'
    findings=[]
    if not isinstance(entry,dict): return [f'[{asset_id}] row is not a JSON object']
    source_link=entry.get('source_link',''); is_exact=entry.get('is_exact_asset_page')
    if not source_link: findings.append(f"[{asset_id}] missing 'source_link'")
    elif looks_like_search_page(source_link):
        findings.append(f"[{asset_id}] source_link looks like a search/category page, not an exact asset page: {source_link}")
        if is_exact is True: findings.append(f"[{asset_id}] is_exact_asset_page=True but URL pattern suggests otherwise — verify manually")
    if is_exact is None: findings.append(f"[{asset_id}] missing 'is_exact_asset_page' flag")
    elif is_exact is False: findings.append(f"[{asset_id}] explicitly flagged as NOT an exact asset page — requires manual verification")
    if not entry.get('license_code') or entry.get('license_code') == 'unknown': findings.append(f"[{asset_id}] license_code missing or 'unknown'")
    if entry.get('risk_flag') == 'high_risk': findings.append(f"[{asset_id}] pre-flagged high_risk — needs extra scrutiny")
    return findings

def load_input(path):
    raw=sys.stdin.read() if path=='-' else open(path,encoding='utf-8').read()
    if not raw.strip(): raise ValueError('No JSON input provided. Pass a file path or pipe JSON with - .')
    return json.loads(raw)

def main():
    ap=argparse.ArgumentParser(description='Lint music/SFX candidate rows before license verification.')
    ap.add_argument('input', help='Path to candidates JSON, or - to read stdin')
    args=ap.parse_args()
    try: data=load_input(args.input)
    except Exception as exc: print(f'ERROR: {exc}', file=sys.stderr); return 2
    entries=data if isinstance(data,list) else [data]
    all_findings=[]
    for entry in entries: all_findings.extend(lint_one(entry))
    if all_findings:
        print('FINDINGS (rows needing attention before license-checker review):')
        for f in all_findings: print(f'  - {f}')
        print(f'\n{len(all_findings)} finding(s) across {len(entries)} candidate(s).')
        return 1
    print(f'All {len(entries)} candidate(s) structurally ready for license-checker review.')
    print('(This does NOT mean they are approved — only that they are complete enough to review.)')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
