#!/usr/bin/env python3
"""
Deterministic check for a clip_scorecard (see shared/contracts/pipeline-artifacts.md).

This does NOT judge creative quality — it only verifies arithmetic/ranges.

Usage:
    python3 tools/validate_clip_score.py path/to/scorecard.json
    cat scorecard.json | python3 tools/validate_clip_score.py -

Expected input: one JSON object or a JSON list of objects containing a `scorecard` object.
"""
import argparse
import json
import sys

MAX_VALUES = {
    "emotional_strength_2": 2,
    "visual_clarity_2": 2,
    "story_relevance_2": 2,
    "audio_commentary_value_1": 1,
    "uniqueness_1": 1,
    "editability_1": 1,
    "rights_reused_content_risk_1": 1,
}
THRESHOLDS = [(8.0, 10.0, "core story clip"),(6.0, 7.9, "supporting clip"),(4.0, 5.9, "context-only / replace"),(0.0, 3.9, "reject")]

def band_for(total):
    for lo, hi, label in THRESHOLDS:
        if lo <= total <= hi:
            return label
    return "out of range"

def validate_one(entry):
    clip_id = entry.get("clip_id", "<unknown>") if isinstance(entry, dict) else "<invalid>"
    sc = entry.get("scorecard") if isinstance(entry, dict) else None
    if not isinstance(sc, dict):
        return [f"[{clip_id}] no 'scorecard' object found"]
    errors=[]; computed_sum=0.0
    for field,maxval in MAX_VALUES.items():
        if field not in sc:
            errors.append(f"[{clip_id}] missing field '{field}'"); continue
        val=sc[field]
        if not isinstance(val,(int,float)):
            errors.append(f"[{clip_id}] field '{field}' is not numeric: {val!r}"); continue
        if val < 0 or val > maxval:
            errors.append(f"[{clip_id}] field '{field}'={val} out of allowed range [0, {maxval}]")
        computed_sum += val
    stated=sc.get('total_10')
    if stated is None:
        errors.append(f"[{clip_id}] missing 'total_10'")
    elif not isinstance(stated,(int,float)):
        errors.append(f"[{clip_id}] 'total_10' is not numeric: {stated!r}")
    elif abs(stated-computed_sum)>0.05:
        errors.append(f"[{clip_id}] stated total_10={stated} does not match sum of components={computed_sum:.2f}")
    else:
        print(f"[{clip_id}] OK — total {stated} -> band: {band_for(stated)}")
    return errors

def load_input(path):
    if path == '-':
        raw=sys.stdin.read()
    else:
        with open(path, encoding='utf-8') as f: raw=f.read()
    if not raw.strip():
        raise ValueError('No JSON input provided. Pass a file path or pipe JSON with - .')
    return json.loads(raw)

def main():
    ap=argparse.ArgumentParser(description='Validate clip_scorecard arithmetic and value ranges.')
    ap.add_argument('input', help='Path to scorecard JSON, or - to read stdin')
    args=ap.parse_args()
    try:
        data=load_input(args.input)
    except Exception as exc:
        print(f'ERROR: {exc}', file=sys.stderr); return 2
    entries=data if isinstance(data,list) else [data]
    all_errors=[]
    for entry in entries: all_errors.extend(validate_one(entry))
    if all_errors:
        print('\nERRORS:')
        for e in all_errors: print(f'  FAIL: {e}')
        return 1
    print('\nAll scorecards internally consistent.'); return 0

if __name__=='__main__':
    raise SystemExit(main())
