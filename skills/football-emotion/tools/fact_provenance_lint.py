#!/usr/bin/env python3
"""
Artifact-aware lint for precise claims without nearby/co-located provenance.

Default behavior is designed for project artifact files, not documentation prose. It parses JSON/YAML
files and fenced json/yaml blocks in Markdown. It skips normal Markdown prose and SKILL.md docs by
default to avoid false positives like "1-2 hours" or scorecard range examples.

Usage:
    python3 tools/fact_provenance_lint.py path/to/project_artifacts
    python3 tools/fact_provenance_lint.py artifact.json
    python3 tools/fact_provenance_lint.py . --include-docs   # noisy audit mode
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

PROVENANCE_KEYS = {
    'provenance','verification_status','source_verification','fact_source','fact_sources',
    'verified_from_source','measured_by','measured_by_tool','measurement_status','confidence',
    'checked_date','source_url_or_reference','source_refs','citation','citations','rights_status',
    'status','user_supplied'
}
PROVENANCE_VALUES = re.compile(r"verified_from_source|measured_by_tool|user_supplied|estimated_by_editor|creative_hypothesis|forbidden_unverified|unverified|needs_more_info", re.I)
PATTERNS = [
    ('percentage', re.compile(r"\b\d+(?:\.\d+)?%\b")),
    ('football_minute', re.compile(r"\b\d{1,3}\+?\d*'\b")),
    ('loudness', re.compile(r"-?\d+(?:\.\d+)?\s*(?:LUFS|dBTP|dB)\b", re.I)),
    ('scoreline', re.compile(r"\b[A-Z]{2,4}\s+\d+\s*[–-]\s*\d+\s+[A-Z]{2,4}\b|\b\d+\s*[–-]\s*\d+\b")),
    ('date_2026_plus', re.compile(r"\b20(?:2[6-9]|[3-9]\d)[-/]\d{1,2}[-/]\d{1,2}\b")),
]
FENCE_RE = re.compile(r"```(?:yaml|yml|json)\s*\n(.*?)\n```", re.I | re.S)
DOC_SKIP_PARTS = {'skills','analysis','implementation','shared/references','shared/contracts','provenance','archive','evals','tools'}


def has_provenance_in_obj(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    for k, v in obj.items():
        if str(k) in PROVENANCE_KEYS:
            return True
        if isinstance(v, str) and PROVENANCE_VALUES.search(v):
            return True
    return False


def precise_matches(text: str):
    out=[]
    for name, rx in PATTERNS:
        for m in rx.finditer(text):
            out.append((name, m.group(0)))
    return out


def walk(obj: Any, path: str='', ancestors: list[dict]|None=None):
    ancestors = ancestors or []
    findings=[]
    if isinstance(obj, dict):
        new_ancestors = ancestors + [obj]
        for k, v in obj.items():
            findings.extend(walk(v, f'{path}.{k}' if path else str(k), new_ancestors))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            findings.extend(walk(v, f'{path}[{i}]', ancestors))
    elif isinstance(obj, (str, int, float)):
        text=str(obj)
        matches=precise_matches(text)
        if matches:
            if not any(has_provenance_in_obj(a) for a in reversed(ancestors[-3:])):
                for kind, val in matches:
                    findings.append((path, kind, val, text[:160]))
    return findings


def parse_structured(text: str, suffix: str):
    if suffix == '.json':
        return json.loads(text)
    if yaml is None:
        raise RuntimeError('PyYAML required for YAML parsing')
    return yaml.safe_load(text)


def lint_file(path: Path, include_docs=False):
    suffix=path.suffix.lower()
    rel_parts=set(str(path).split('/'))
    if not include_docs:
        # Skip package documentation/prose; default mode is for project artifact directories.
        as_posix=path.as_posix()
        doc_names = {'README.md','CHANGELOG_V2_FIXES.md','CHANGELOG_V3_EDITORIAL_JOURNEY.md','CHANGELOG_V4_REPO_BRIDGE.md','CHANGELOG_V5_SAFETY_EXECUTION_PATCHES.md','CHANGELOG_V6_RUNTIME_GUARDRAILS.md','validation_report.md','ZIP_VALIDATION_REPORT.md'}
        if path.name == 'SKILL.md' or path.name in doc_names or any(part in as_posix for part in DOC_SKIP_PARTS):
            return []
    findings=[]
    text=path.read_text(encoding='utf-8', errors='ignore')
    if suffix in {'.json','.yaml','.yml'}:
        try:
            obj=parse_structured(text,suffix)
            return walk(obj)
        except Exception as exc:
            return [('<parse>', 'parse_error', str(exc), 'Could not parse structured artifact')]
    if suffix == '.md':
        for n, block in enumerate(FENCE_RE.findall(text), start=1):
            try:
                if block.strip().startswith('{') or block.strip().startswith('['):
                    obj=json.loads(block)
                elif yaml is not None:
                    obj=yaml.safe_load(block)
                else:
                    continue
                for f in walk(obj, path=f'fenced_block[{n}]'):
                    findings.append(f)
            except Exception:
                continue
        if include_docs:
            # Noisy fallback: scan lines with nearby provenance window.
            lines=text.splitlines()
            for i,line in enumerate(lines):
                for kind,val in precise_matches(line):
                    window='\n'.join(lines[max(0,i-2):min(len(lines),i+3)])
                    if not PROVENANCE_VALUES.search(window) and 'provenance' not in window.lower():
                        findings.append((f'line {i+1}', kind, val, line.strip()[:160]))
    return findings


def collect_files(root: Path, include_docs=False):
    if root.is_file():
        return [root]
    exts={'.json','.yaml','.yml','.md'}
    return [p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in exts and (include_docs or 'provenance/source_pack' not in p.as_posix())]


def main():
    ap=argparse.ArgumentParser(description='Lint artifact-shaped JSON/YAML/fenced blocks for precise claims without provenance.')
    ap.add_argument('path', help='Artifact file or directory')
    ap.add_argument('--include-docs', action='store_true', help='Also scan free-text documentation; noisy, for audits only')
    args=ap.parse_args()
    root=Path(args.path)
    if not root.exists():
        print(f'ERROR: path not found: {root}', file=sys.stderr); return 2
    all_findings=[]
    for f in collect_files(root, include_docs=args.include_docs):
        for loc, kind, val, text in lint_file(f, include_docs=args.include_docs):
            all_findings.append((f, loc, kind, val, text))
    for f, loc, kind, val, text in all_findings:
        print(f'{f}:{loc}: {kind} precise claim {val!r} lacks co-located provenance: {text}')
    if all_findings:
        print(f'\n{len(all_findings)} provenance finding(s).')
        return 1
    print('No artifact provenance issues found.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
