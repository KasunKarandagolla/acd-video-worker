#!/usr/bin/env python3
"""Reject fake quantified learning in Hermes memory drafts."""
import re, sys
from pathlib import Path
BAD = [
    re.compile(r"\b\d+(?:\.\d+)?%\b.*\b(increase|improvement|better|retention|tension)", re.I),
    re.compile(r"\blegal(?:ly)? safe\b", re.I),
    re.compile(r"\bguaranteed\b", re.I),
]
if len(sys.argv)<2:
    print('Usage: memory_claim_lint.py <memory-file>')
    sys.exit(2)
path=Path(sys.argv[1])
text=path.read_text(encoding='utf-8', errors='ignore')
errors=[]
for rx in BAD:
    for m in rx.finditer(text):
        errors.append(m.group(0))
if 'evidence_type' not in text:
    errors.append('missing evidence_type field')
if errors:
    print('MEMORY CLAIM LINT FAILED')
    for e in errors: print('-', e)
    sys.exit(1)
print('MEMORY CLAIM LINT PASSED')
