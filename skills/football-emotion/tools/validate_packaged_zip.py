#!/usr/bin/env python3
"""Validate a packaged football emotion skill-system ZIP after packaging."""
import sys, zipfile, tempfile, subprocess
from pathlib import Path

if len(sys.argv) < 2:
    print("Usage: validate_packaged_zip.py <package.zip>", file=sys.stderr)
    sys.exit(2)

zip_path = Path(sys.argv[1]).resolve()
if not zip_path.exists():
    print(f"ERROR: zip not found: {zip_path}", file=sys.stderr)
    sys.exit(1)

with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(tmp)
    roots = [p for p in tmp.iterdir() if p.is_dir()]
    if len(roots) != 1:
        print(f"ERROR: expected exactly one root folder in zip, found {len(roots)}")
        sys.exit(1)
    root = roots[0]
    errors = []
    for skill_dir in sorted((root / "skills").iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            errors.append(f"Missing SKILL.md: {skill_dir.name}")
        elif skill_md.stat().st_size < 200:
            errors.append(f"SKILL.md too small/empty: {skill_dir.name}")
    validator = root / "tools" / "validate_skill_system.py"
    if not validator.exists():
        errors.append("Missing tools/validate_skill_system.py")
    else:
        proc = subprocess.run([sys.executable, str(validator), str(root)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        print(proc.stdout)
        if proc.returncode != 0:
            errors.append("validate_skill_system.py failed")
    if errors:
        print("ZIP VALIDATION FAILED")
        for e in errors:
            print(f"- {e}")
        sys.exit(1)
    print("ZIP VALIDATION PASSED")
