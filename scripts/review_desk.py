#!/usr/bin/env python3
"""Local-only image organization. Run: python scripts/review_desk.py"""
import argparse
import copy
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import mimetypes
import os
from pathlib import Path
import secrets
import subprocess
import sys
from urllib.parse import urlsplit
import uuid

import review_metadata as meta
import review_workspace as workspace

ROOT = Path(__file__).resolve().parents[1]


def atomic_json(path, value):
    meta.safe_path(path.parent, path.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp-' + secrets.token_hex(8))
    try:
        with temporary.open('x', encoding='utf-8') as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


class Desk:
    def __init__(self, root, manifest=None):
        self.root = Path(root)
        self.library = meta.safe_path(self.root, 'resources/character-library')
        self.public_path = meta.safe_path(self.root, meta.PUBLIC_PATH)
        self.private_dir = meta.safe_path(self.root, '.review-desk')
        self.private_path = meta.safe_path(self.root, '.review-desk/local.json')
        self.journal = meta.safe_path(self.root, '.review-desk/pending.json')
        self.manifest = manifest or json.loads(meta.safe_path(self.library, 'manifest.json').read_text(encoding='utf-8'))
        self.images = {a['sha256']: a for a in self.manifest['assets'] if meta.is_image(a)}
        self.private_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.private_dir.chmod(0o700)
        except OSError:
            pass
        # Refuse to serve personal notes accidentally added to the index.
        result = subprocess.run(['git', 'ls-files', '--', '.review-desk'], cwd=self.root,
                                capture_output=True, text=True)
        meta.require(not result.stdout.strip(), 'Private .review-desk files are tracked by Git; untrack them first')
        ignored = subprocess.run(['git', 'check-ignore', '--no-index', '--', '.review-desk/local.json'],
                                 cwd=self.root, capture_output=True, text=True)
        meta.require(result.returncode != 0 or ignored.returncode == 0,
                     'Add .review-desk/ to .gitignore before starting')
        self.public = meta.load_metadata(self.root, self.manifest)
        self.private = json.loads(self.private_path.read_text(encoding='utf-8')) if self.private_path.exists() else {
            'version': 0, 'notes': {}, 'history': []}
        if self.journal.exists():
            self.recover()
        workspace.validate_private(self.private, self.public, self.images)
        meta.validate_locations(self.library, self.manifest, self.public)

    def current(self):
        # External changes must not be silently overwritten by a running desk.
        meta.require(meta.load_metadata(self.root, self.manifest) == self.public,
                     'Organization changed outside this session. Restart the Review Desk.')
        if self.private_path.exists():
            meta.require(json.loads(self.private_path.read_text(encoding='utf-8')) == self.private,
                         'Private records changed outside this session. Restart the Review Desk.')

    def path(self, sha, state=None):
        return meta.locate(self.library, self.images[sha]['resource_path'], self.manifest, state or self.public)

    def moves(self, before, after):
        for sha in sorted(set(before['archived']) ^ set(after['archived'])):
            source, target = self.path(sha, before), self.path(sha, after)
            meta.require(source.is_file() and meta.digest(source) == sha, 'Archive source changed; operation cancelled')
            meta.require(not target.exists(), 'Archive destination already exists; nothing overwritten')
            yield source, target

    def recover(self):
        record = json.loads(self.journal.read_text(encoding='utf-8'))
        before, after = record['before'], record['after']
        meta.validate_metadata(before, self.manifest); meta.validate_metadata(after, self.manifest)
        workspace.validate_private(record['private_before'], before, self.images)
        # A crash rolls the entire pending operation back to its recorded start.
        for sha in sorted(set(before['archived']) ^ set(after['archived'])):
            source, target = self.path(sha, before), self.path(sha, after)
            if target.exists():
                meta.require(not source.exists() and meta.digest(target) == sha, 'Cannot safely recover archive transaction')
                source.parent.mkdir(parents=True, exist_ok=True); target.rename(source)
            meta.require(source.is_file() and meta.digest(source) == sha, 'Recovery source missing or changed')
        if meta.load_metadata(self.root, self.manifest) != before:
            atomic_json(self.public_path, before)
        atomic_json(self.private_path, record['private_before'])
        self.public = before; self.private = record['private_before']
        self.refresh_indexes()
        self.journal.unlink()

    def refresh_indexes(self):
        # Update live navigation only, never archived historical documents.
        import resource_library
        previous_root, previous_library = resource_library.ROOT, resource_library.LIBRARY
        resource_library.ROOT, resource_library.LIBRARY = self.root, self.library
        try:
            for name, text in resource_library.rendered_indexes(self.manifest).items():
                path = self.library / name
                if path.exists():
                    temporary = path.with_name(name + '.tmp-' + secrets.token_hex(8))
                    temporary.write_text(text, encoding='utf-8'); os.replace(temporary, path)
        finally:
            resource_library.ROOT, resource_library.LIBRARY = previous_root, previous_library

    def commit(self, public, private):
        meta.validate_metadata(public, self.manifest)
        workspace.validate_private(private, public, self.images)
        operations = list(self.moves(self.public, public))
        meta.require(not self.journal.exists(), 'A pending transaction needs recovery before another change')
        atomic_json(self.journal, {'before': self.public, 'after': public, 'private_before': self.private})
        try:
            for source, target in operations:
                target.parent.mkdir(parents=True, exist_ok=True)
                meta.safe_path(self.library, target.relative_to(self.library).as_posix())
                source.rename(target)
            if public != self.public:
                atomic_json(self.public_path, public)
            atomic_json(self.private_path, private)
            self.public, self.private = public, private
            if operations:
                self.refresh_indexes()
            self.journal.unlink()
        except Exception:
            self.recover()
            raise

    def state(self):
        refs = {}
        for reference in self.manifest['references']:
            for sha in reference['asset_sha256']:
                refs.setdefault(sha, []).append(reference)
        assets = []
        for sha, asset in self.images.items():
            assets.append({**asset, 'references': refs.get(sha, []), 'url': '/image/' + sha,
                           'archived': sha in self.public['archived']})
        return {'public': self.public, 'notes': self.private['notes'], 'assets': assets,
                'workspace': self.private.get('workspace', workspace.empty()),
                'version': self.private['version'], 'undo_count': len(self.private['history'])}

    def mutate(self, payload):
        self.current()
        meta.require(isinstance(payload, dict) and payload.get('version') == self.private['version'],
                     'Stale tab. Reload before making another change.')
        action = payload.get('action')
        public, private = copy.deepcopy(self.public), copy.deepcopy(self.private)
        if action == 'undo':
            meta.require(bool(private['history']), 'Nothing to undo')
            last = private['history'].pop()
            public = last['public']; private['notes'] = last['notes']
            private['workspace'] = last.get('workspace', workspace.empty())
        else:
            private['history'].append({'public': copy.deepcopy(self.public), 'notes': copy.deepcopy(private['notes']),
                                       'workspace': copy.deepcopy(private.get('workspace', workspace.empty()))})
            private.setdefault('workspace', workspace.empty())
            private['history'] = private['history'][-100:]
            if action == 'collection_create':
                public['collections'].append({'id': 'collection-' + uuid.uuid4().hex,
                                             'name': payload.get('name'), 'assets': [], 'details': []})
            elif action in {'collection_rename', 'collection_delete', 'collection_assign'}:
                collection = next((c for c in public['collections'] if c['id'] == payload.get('id')), None)
                meta.require(collection is not None, 'Unknown collection')
                if action == 'collection_delete':
                    public['collections'].remove(collection)
                elif action == 'collection_rename':
                    collection['name'] = payload.get('name')
                else:
                    for key, allowed in [('assets', set(self.images)), ('details', {d['id'] for d in public['details']})]:
                        values = payload.get(key, [])
                        meta.require(isinstance(values, list) and all(isinstance(v, str) for v in values)
                                     and set(values) <= allowed, 'Unknown collection item')
                        if payload.get('remove') is True:
                            collection[key] = [v for v in collection[key] if v not in values]
                        else:
                            collection[key] = list(dict.fromkeys(collection[key] + values))
            elif action == 'detail_save':
                public['details'].append({'id': 'view-' + uuid.uuid4().hex, 'title': payload.get('title'),
                                          'asset_sha256': payload.get('asset_sha256'), 'rect': payload.get('rect')})
            elif action == 'detail_delete':
                identity = payload.get('id')
                meta.require(any(d['id'] == identity for d in public['details']), 'Unknown detail view')
                public['details'] = [d for d in public['details'] if d['id'] != identity]
                for collection in public['collections']:
                    collection['details'] = [d for d in collection['details'] if d != identity]
                private['notes'].pop(identity, None)
                workspace.remove_target(private['workspace'], identity)
            elif action in {'archive', 'restore'}:
                ids = payload.get('assets')
                meta.require(isinstance(ids, list) and ids and all(isinstance(v, str) for v in ids)
                             and set(ids) <= self.images.keys(), 'Select known public images only')
                if action == 'archive':
                    public['archived'] = list(dict.fromkeys(public['archived'] + ids))
                else:
                    public['archived'] = [s for s in public['archived'] if s not in ids]
            elif action == 'note':
                identity, note = payload.get('id'), payload.get('text')
                meta.require(isinstance(identity, str) and identity in
                             (set(self.images) | {d['id'] for d in public['details']}), 'Unknown note target')
                meta.require(isinstance(note, str) and len(note) <= 20000, 'Notes are limited to 20,000 characters')
                private['notes'][identity] = note
            elif action in {'annotation_save', 'annotation_delete', 'comparison_save', 'comparison_delete'}:
                workspace.mutate(private['workspace'], payload)
            else:
                raise ValueError('Unknown review action')
        public['revision'] = self.public['revision'] + (public != self.public)
        private['version'] = self.private['version'] + 1
        self.commit(public, private)
        return self.state()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Never log notes or user-supplied payloads.
        pass

    def trusted(self, write=False):
        host = self.headers.get('Host', '')
        port = self.server.server_port
        meta.require(host in {f'127.0.0.1:{port}', f'localhost:{port}'}, 'Invalid local Host')
        origin = self.headers.get('Origin')
        meta.require(origin is None or origin == 'http://' + host, 'Cross-origin requests are forbidden')
        meta.require(self.headers.get('Sec-Fetch-Site') not in {'cross-site', 'same-site'}, 'Cross-site request forbidden')
        if write:
            meta.require(secrets.compare_digest(self.headers.get('X-Review-Token', ''), self.server.token), 'Invalid session token')
            meta.require(self.headers.get('Content-Type', '').split(';')[0] == 'application/json', 'JSON required')

    def send(self, body, content_type='application/json', status=200):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        try:
            self.trusted()
            path = urlsplit(self.path).path
            if path == '/api/state':
                self.server.desk.current()
                self.send({**self.server.desk.state(), 'token': self.server.token})
            elif path.startswith('/image/'):
                sha = path.removeprefix('/image/')
                meta.require(sha in self.server.desk.images, 'Unknown image')
                source = self.server.desk.path(sha)
                meta.require(source.is_file() and meta.digest(source) == sha, 'Image integrity check failed')
                self.send(source.read_bytes(), mimetypes.guess_type(source.name)[0] or 'application/octet-stream')
            elif path in {'/', '/desk.js', '/desk.css', '/annotations.js', '/workspace.css', '/comparison.js'}:
                source = Path(__file__).resolve().parents[1] / 'web/review-desk' / ({'/': 'index.html'}.get(path, path[1:]))
                self.send(source.read_bytes(), {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
                                               '.css': 'text/css; charset=utf-8'}[source.suffix])
            else:
                self.send({'error': 'Not found'}, status=404)
        except (ValueError, OSError, KeyError) as error:
            self.send({'error': str(error)}, status=400)

    def do_POST(self):
        try:
            self.trusted(write=True)
            meta.require(urlsplit(self.path).path == '/api/change', 'Unknown endpoint')
            length = int(self.headers.get('Content-Length', '0'))
            meta.require(0 < length <= 1024 * 1024, 'Invalid request size')
            payload = json.loads(self.rfile.read(length))
            self.send(self.server.desk.mutate(payload))
        except (ValueError, OSError, KeyError, TypeError) as error:
            self.send({'error': str(error)}, status=400)


class RepoLock:
    """OS-held lock; automatically released even if the process exits abnormally."""
    def __init__(self, root):
        path = meta.safe_path(root, '.review-desk/server.lock')
        path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = path.open('a+b')
        try:
            if os.name == 'nt':
                import msvcrt
                self.stream.seek(0); self.stream.write(b'0'); self.stream.flush(); self.stream.seek(0)
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.stream.close()
            raise ValueError('Another Review Desk is already running for this repo')

    def close(self):
        self.stream.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    lock = None
    try:
        lock = RepoLock(ROOT)
        import resource_library
        manifest = resource_library.load_manifest()
        desk = Desk(ROOT, manifest)  # Recover an interrupted move before validating navigation.
        resource_library.validate(manifest)
        server = HTTPServer(('127.0.0.1', args.port), Handler)
        server.desk = desk; server.token = secrets.token_urlsafe(32)
        print(f'Review Desk: http://127.0.0.1:{server.server_port}', flush=True)
        print('Local only. Notes and undo history stay in ignored .review-desk/. Ctrl+C stops.', flush=True)
        try:
            server.serve_forever()
        finally:
            server.server_close()
    except KeyboardInterrupt:
        pass
    except (ValueError, OSError) as error:
        print('ERROR:', error, file=sys.stderr)
        return 1
    finally:
        if lock:
            lock.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
