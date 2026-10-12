"""Public organization only. Recovery records and artwork remain immutable."""
import hashlib
import json
import math
from pathlib import Path
import re
from windows_paths import path_errors

PUBLIC_PATH = 'data/review-desk.json'
ARCHIVE = 'Archive/ReviewDesk'
IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def is_image(asset):
    return Path(asset['stored_filename']).suffix.lower() in IMAGE_SUFFIXES


def safe_path(base, relative):
    require(isinstance(relative, str) and relative and '\\' not in relative
            and '\x00' not in relative and not re.match(r'^[A-Za-z]:', relative)
            and all(p not in {'', '.', '..'} for p in relative.split('/')),
            'Unsafe relative path')
    require(not path_errors([relative]), 'Windows-incompatible relative path')
    base = Path(base)
    require(not base.is_symlink(), 'Symlink base is not supported')
    target = base / relative
    require(target.resolve().is_relative_to(base.resolve()), 'Path escapes its base')
    current = target
    while current != base:
        require(not current.is_symlink(), 'Symlinks are not supported')
        current = current.parent
    return target


def default_metadata():
    return {'schema_version': 1, 'revision': 0, 'collections': [], 'details': [], 'archived': []}


def validate_metadata(data, manifest):
    require(isinstance(data, dict) and set(data) ==
            {'schema_version', 'revision', 'collections', 'details', 'archived'},
            'Public organization has unknown fields (private notes are forbidden)')
    require(type(data['schema_version']) is int and data['schema_version'] == 1,
            'Unsupported organization schema')
    require(type(data['revision']) is int and data['revision'] >= 0, 'Invalid revision')
    images = {a['sha256'] for a in manifest['assets'] if is_image(a)}
    for field in ('collections', 'details', 'archived'):
        require(isinstance(data[field], list) and len(data[field]) <= 10000, 'Invalid ' + field)

    def label(value):
        require(isinstance(value, str) and 0 < len(value.strip()) <= 160
                and not any(ord(c) < 32 for c in value), 'Labels must be 1–160 printable characters')
        # Public labels must not contain private service markers or machine paths.
        from resource_library import OWNER_ID, OWNER_PATH, PRIVATE_URL
        require(not any(p.search(value) for p in (OWNER_ID, OWNER_PATH, PRIVATE_URL)),
                'Private identifier or path in a public label')

    def identity(value):
        require(isinstance(value, str) and re.fullmatch(r'[a-z0-9-]{1,64}', value), 'Invalid organization ID')

    def unique(values, allowed, kind):
        require(isinstance(values, list) and all(isinstance(x, str) for x in values)
                and len(values) == len(set(values)) and set(values) <= allowed, 'Invalid ' + kind)

    details = set()
    for detail in data['details']:
        require(isinstance(detail, dict) and set(detail) == {'id', 'title', 'asset_sha256', 'rect'},
                'Invalid detail-view fields')
        identity(detail['id']); label(detail['title'])
        require(detail['id'] not in details, 'Duplicate detail-view ID')
        details.add(detail['id'])
        require(detail['asset_sha256'] in images, 'Detail parent must be a registered public image asset')
        rect = detail['rect']
        require(isinstance(rect, list) and len(rect) == 4
                and all(type(x) in (int, float) and math.isfinite(x) and 0 <= x <= 1 for x in rect),
                'Detail bounds must be finite normalized coordinates')
        require(rect[0] < rect[2] and rect[1] < rect[3], 'Detail region must have positive area')
    collections = set()
    for collection in data['collections']:
        require(isinstance(collection, dict) and set(collection) == {'id', 'name', 'assets', 'details'},
                'Invalid collection fields')
        identity(collection['id']); label(collection['name'])
        require(collection['id'] not in collections, 'Duplicate collection ID')
        collections.add(collection['id'])
        unique(collection['assets'], images, 'collection assets')
        unique(collection['details'], details, 'collection detail views')
    unique(data['archived'], images, 'archive identities')
    return data


def load_metadata(root, manifest):
    path = safe_path(root, PUBLIC_PATH)
    return validate_metadata(json.loads(path.read_text(encoding='utf-8')) if path.exists()
                             else default_metadata(), manifest)


def asset_relative(asset, metadata):
    relative = asset['resource_path']
    return ARCHIVE + '/' + relative if asset['sha256'] in metadata['archived'] else relative


def locate(library, relative, manifest, metadata):
    asset = next((a for a in manifest['assets'] if a['resource_path'] == relative), None)
    return safe_path(library, asset_relative(asset, metadata) if asset else relative)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate_locations(library, manifest, metadata):
    for asset in manifest['assets']:
        path = locate(library, asset['resource_path'], manifest, metadata)
        require(path.is_file() and digest(path) == asset['sha256'],
                'Missing or changed asset: ' + asset['stored_filename'])
        alternate = safe_path(library, (asset['resource_path'] if asset['sha256'] in metadata['archived']
                                       else ARCHIVE + '/' + asset['resource_path']))
        require(not alternate.exists(), 'Unexpected second copy at archive location')
    expected = {asset_relative(a, metadata) for a in manifest['assets']}
    actual = {p.relative_to(library).as_posix() for folder in ('resources', ARCHIVE)
              for p in (library / folder).rglob('*') if p.is_file() or p.is_symlink()}
    require(actual == expected, 'Unexpected or missing files in the asset store')
