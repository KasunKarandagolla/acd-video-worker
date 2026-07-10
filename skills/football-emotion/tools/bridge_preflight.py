#!/usr/bin/env python3
"""
Inspect local Hermes-Agent and OpenMontage repos for the football-emotion bridge.

This script does not modify either repo. It writes a markdown report and, when possible,
OpenMontage provider menu JSON files.

Usage:
    python3 tools/bridge_preflight.py [base_path] [output_path]
    python3 tools/bridge_preflight.py --base /home/kasun/Music/Director --output /tmp/preflight.md
    python3 tools/bridge_preflight.py --stdout

If the default base path does not exist, the report is written to stdout unless an explicit
--output is provided. This keeps the tool portable outside the original author's machine.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

DEFAULT_ROOT = Path('/home/kasun/Music/Director')


def run(cmd, cwd=None, timeout=60):
    try:
        out = subprocess.check_output(cmd, cwd=cwd, stderr=subprocess.STDOUT, text=True, timeout=timeout)
        return True, out.strip()
    except Exception as exc:
        return False, str(exc)


def git_head(path: Path):
    if not (path / '.git').exists():
        return 'not a git repo or .git missing'
    ok, out = run(['git', 'rev-parse', 'HEAD'], cwd=path)
    return out if ok else f'error: {out}'


def git_remote(path: Path):
    if not (path / '.git').exists():
        return 'not a git repo or .git missing'
    ok, out = run(['git', 'remote', 'get-url', 'origin'], cwd=path)
    return out if ok else f'error: {out}'


def list_existing(path: Path, rels):
    return {rel: (path / rel).exists() for rel in rels}


def build_report(base: Path, out_dir: Path | None = None):
    hermes = base / 'Hermes-Agent'
    openm = base / 'OpenMontage'
    lines = []
    lines.append('# Football Emotion Repo Bridge Preflight')
    lines.append('')
    lines.append(f'Base path: `{base}`')
    lines.append('')
    lines.append('## Repo setup status')
    missing = []
    for label, path in [('Hermes-Agent', hermes), ('OpenMontage', openm)]:
        if not path.exists():
            missing.append(str(path))
    allowed = 'proceed' if not missing else 'simulate_only'
    lines.append('```yaml')
    lines.append('repo_setup_status:')
    lines.append(f'  hermes_path: {hermes}')
    lines.append(f'  hermes_exists: {str(hermes.exists()).lower()}')
    lines.append(f'  openmontage_path: {openm}')
    lines.append(f'  openmontage_exists: {str(openm.exists()).lower()}')
    lines.append(f'  preflight_possible: {str(not missing).lower()}')
    lines.append(f'  allowed_next_action: {allowed}')
    lines.append('  missing_items:')
    if missing:
        for item in missing:
            lines.append(f'    - {item}')
    else:
        lines.append('    []')
    lines.append('```')
    lines.append('')
    lines.append('## Repo presence')
    for name, path in [('Hermes-Agent', hermes), ('OpenMontage', openm)]:
        lines.append(f'- {name}: `{path}` — {"FOUND" if path.exists() else "MISSING"}')
        if path.exists():
            lines.append(f'  - git HEAD: `{git_head(path)}`')
            lines.append(f'  - git remote origin: `{git_remote(path)}`')
    lines.append('')
    if hermes.exists():
        lines.append('## Hermes key paths')
        for rel, exists in list_existing(hermes, ['skills','optional-skills','tools','providers','agent','hermes_cli','gateway','mcp_serve.py','run_agent.py']).items():
            lines.append(f'- `{rel}`: {"FOUND" if exists else "missing"}')
        lines.append('')
    if openm.exists():
        lines.append('## OpenMontage key paths')
        for rel, exists in list_existing(openm, ['AGENT_GUIDE.md','PROJECT_CONTEXT.md','pipeline_defs','pipeline_defs/documentary-montage.yaml','skills','skills/pipelines','.agents/skills','tools','tools/tool_registry.py','schemas','schemas/artifacts','backlot','remotion-composer','music_library']).items():
            lines.append(f'- `{rel}`: {"FOUND" if exists else "missing"}')
        lines.append('')
        py = "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.provider_menu_summary(), indent=2))"
        ok, out = run([sys.executable, '-c', py], cwd=openm, timeout=90)
        lines.append('## OpenMontage provider menu summary')
        if ok:
            json_path = (out_dir or base) / 'openmontage_provider_menu_summary.json'
            try:
                json_path.parent.mkdir(parents=True, exist_ok=True)
                json_path.write_text(out + '\n', encoding='utf-8')
                lines.append(f'- Provider menu summary: SUCCESS, saved to `{json_path}`')
            except Exception as exc:
                lines.append(f'- Provider menu summary: SUCCESS, but could not write JSON file: {exc}')
            lines.append('```json')
            lines.append(out[:8000])
            if len(out) > 8000:
                lines.append('... truncated in report ...')
            lines.append('```')
        else:
            lines.append('- Provider menu summary: FAILED')
            lines.append('```text')
            lines.append(out)
            lines.append('```')
        lines.append('')
    return '\n'.join(lines) + '\n'


def parse_args():
    ap = argparse.ArgumentParser(description='Inspect Hermes-Agent and OpenMontage local repos for the football-emotion bridge.')
    ap.add_argument('positional_base', nargs='?', help='Base folder containing Hermes-Agent and OpenMontage, e.g. /home/kasun/Music/Director')
    ap.add_argument('positional_output', nargs='?', help='Optional markdown report output path')
    ap.add_argument('--base', dest='base', help='Base folder containing Hermes-Agent and OpenMontage')
    ap.add_argument('--output', '-o', dest='output', help='Markdown report output path')
    ap.add_argument('--stdout', action='store_true', help='Print report to stdout instead of writing a file')
    return ap.parse_args()


def main():
    args = parse_args()
    base = Path(args.base or args.positional_base or DEFAULT_ROOT).expanduser().resolve()
    explicit_output = args.output or args.positional_output
    if explicit_output:
        out_path = Path(explicit_output).expanduser().resolve()
    elif base.exists() and not args.stdout:
        out_path = base / 'football_emotion_repo_bridge_preflight.md'
    else:
        out_path = None
    report = build_report(base, out_dir=(out_path.parent if out_path else Path.cwd()))
    if args.stdout or out_path is None:
        print(report, end='')
        if out_path is None and not base.exists():
            print('\nNOTE: Default base path is missing; report printed to stdout. Pass --output to save it.', file=sys.stderr)
        return 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding='utf-8')
    print(f'Wrote {out_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
