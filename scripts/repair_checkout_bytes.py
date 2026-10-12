#!/usr/bin/env python3
"""Repair only proven Git LF-to-CRLF checkout conversions; preserve other edits."""
import argparse
import os
from pathlib import Path
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PROTECTED = ('resources/character-library', 'docs')


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, stderr=subprocess.PIPE)


def inspect(root):
    if subprocess.run(['git', 'diff', '--cached', '--quiet', '--', *PROTECTED], cwd=root).returncode:
        raise ValueError('Protected files have staged changes. Commit or unstage those changes before repairing.')
    candidates, conflicts = [], []
    for entry in git(root, 'ls-tree', '-rz', 'HEAD', '--', *PROTECTED).split(b'\0'):
        if not entry:
            continue
        header, encoded_path = entry.split(b'\t', 1)
        mode, kind, sha = header.decode().split()
        relative = encoded_path.decode('utf-8'); path = root / relative
        # Inspect all protected paths. Dotfiles and extensionless text assets
        # can also be converted by Git; filename suffixes cannot classify them.
        # Never recreate a missing/moved file or follow a symlink.
        if not path.exists():
            continue
        if mode not in ('100644', '100755') or kind != 'blob' or path.is_symlink() \
                or any(parent.is_symlink() for parent in path.parents if parent != root) \
                or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('Unsafe protected path: ' + relative)
        original = git(root, 'cat-file', 'blob', sha); current = path.read_bytes()
        if current == original:
            continue
        # Exact proof, not a whitespace-normalized comparison. Originals with
        # CRLF/mixed line endings are never normalized or "repaired".
        if b'\0' not in original and b'\r' not in original \
                and current == original.replace(b'\n', b'\r\n'):
            candidates.append((path, current, original))
        else:
            conflicts.append(relative)
    return candidates, conflicts


def repair(root, apply=False):
    candidates, conflicts = inspect(root)
    for relative in conflicts:
        print('Unchanged by repair (other local edits):', relative)
    for path, current, original in candidates:
        print(('Repairing:' if apply else 'Would repair:'), path.relative_to(root).as_posix())
        if apply:
            if path.is_symlink() or path.read_bytes() != current:
                raise ValueError('File changed during repair; stopped without overwriting it')
            temporary = path.with_name(path.name + '.repair-' + secrets.token_hex(8))
            try:
                with temporary.open('xb') as stream:
                    stream.write(original); stream.flush(); os.fsync(stream.fileno())
                temporary.chmod(path.stat().st_mode & 0o777)
                os.replace(temporary, path)
            finally:
                if temporary.exists():
                    temporary.unlink()
    print(f'{len(candidates)} exact line-ending conversion(s) ' + ('repaired.' if apply else 'found. Use --apply to repair.'))
    return len(candidates), conflicts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Restore proven conversions to exact HEAD bytes')
    args = parser.parse_args()
    try:
        repair(ROOT, args.apply)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print('ERROR:', error, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
