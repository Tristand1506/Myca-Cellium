"""Reject repository paths that cannot be checked out on ordinary Windows."""
from pathlib import Path
import re
import subprocess

INVALID = re.compile(r'[<>:"\\|?*\x00-\x1f]')
RESERVED = re.compile(r'^(?:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³]|CONIN\$|CONOUT\$)$', re.I)


def path_errors(paths):
    errors = []
    spellings = {}
    for path in paths:
        parts = path.split('/')
        for index, part in enumerate(parts):
            if (not part or part in {'.', '..'} or INVALID.search(part)
                    or part.endswith((' ', '.'))
                    or RESERVED.fullmatch(part.split('.')[0].rstrip(' '))
                    or len(part.encode('utf-16-le')) // 2 > 255):
                errors.append(f'Windows-incompatible path: {path}')
                break
            prefix = '/'.join(parts[:index + 1])
            key = prefix.casefold()
            if key in spellings and spellings[key] != prefix:
                errors.append(f'Case-insensitive path collision: {spellings[key]} / {prefix}')
            spellings[key] = prefix
    return sorted(set(errors))


def repository_paths(root):
    # Include new staged/unstaged files but honor .gitignore and exclude outputs.
    result = subprocess.run(['git', '-C', str(root), 'ls-files', '-z', '--cached',
                             '--others', '--exclude-standard'], check=True, capture_output=True)
    return [path for path in result.stdout.decode('utf-8').split('\0') if path]


def validate_repository(root):
    paths = repository_paths(root)
    errors = path_errors(paths)
    if errors:
        raise ValueError('\n'.join(errors))
    return len(paths)


if __name__ == '__main__':
    count = validate_repository(Path(__file__).resolve().parents[1])
    print(f'Windows path validation passed for {count} repository files')
