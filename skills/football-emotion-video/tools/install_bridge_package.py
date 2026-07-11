#!/usr/bin/env python3
"""Copy/symlink this skill package into a local Hermes-Agent optional-skills area."""
import argparse, shutil
from pathlib import Path
DEFAULT_BASE = Path('/home/kasun/Music/Director')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--package-root', default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument('--hermes-root', default=str(DEFAULT_BASE/'Hermes-Agent'))
    ap.add_argument('--copy', action='store_true')
    args = ap.parse_args()
    package_root = Path(args.package_root).resolve()
    hermes_root = Path(args.hermes_root).resolve()
    target = hermes_root/'optional-skills'/'creative'/'football-emotion-video'
    if not hermes_root.exists():
        raise SystemExit(f'Hermes root missing: {hermes_root}')
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        if target.is_symlink() or target.is_file():
            target.unlink()
        else:
            shutil.rmtree(target)
    if args.copy:
        shutil.copytree(package_root, target)
        mode = 'copied'
    else:
        target.symlink_to(package_root, target_is_directory=True)
        mode = 'symlinked'
    print(f'{mode}: {package_root} -> {target}')

if __name__ == '__main__':
    main()
