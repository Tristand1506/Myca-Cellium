"""Isolated store/HTTP tests; never mutate the real recovered artwork."""
import base64
import copy
import hashlib
from http.client import HTTPConnection
from http.server import HTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_site
import resource_library
import review_desk
import review_metadata as meta
from review_public import organization_pages
from site_gallery import gallery_pages

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aM1sAAAAASUVORK5CYII=')


def fixture(root):
    library = root / 'resources/character-library'
    assets, refs = [], []
    for index, (rid, name, classification) in enumerate([
        ('R08', 'R08 lichen.png', ['supporting historical reference; no whole-sheet canon approval']),
        ('R33', 'R33 Myca: membrane.png', ['experiment', 'experimental membrane design'])]):
        raw = PNG + bytes([index])
        sha = hashlib.sha256(raw).hexdigest()
        relative = f'resources/{sha[:16]}/{name}'
        path = library / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
        assets.append({'sha256': sha, 'resource_path': relative, 'stored_filename': name,
                       'original_filename': name, 'filename_aliases': [name], 'size_bytes': len(raw),
                       'classification': classification, 'original_bytes': True})
        refs.append({'reference_id': rid, 'asset_sha256': [sha], 'status': 'recovered',
                     'design_registry': {'reference_id': rid, 'title': rid + ' selected features',
                                         'status': 'Experimental' if rid == 'R33' else 'Selected lichen only',
                                         'approved_scope': 'Use lichen only', 'known_defects': 'Do not inherit cap height'}})
    manifest = {'schema_version': '1.0', 'assets': assets, 'references': refs}
    (library / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    data = meta.default_metadata(); data['collections'] = [{'id': 'lichen', 'name': 'Lichen', 'assets': [], 'details': []}]
    (root / 'data').mkdir(); (root / meta.PUBLIC_PATH).write_text(json.dumps(data), encoding='utf-8')
    (root / '.gitignore').write_text('.review-desk/\n', encoding='utf-8')
    return manifest


class DeskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.manifest = fixture(self.root)
        self.desk = review_desk.Desk(self.root, self.manifest)
        self.sha = self.manifest['assets'][0]['sha256']

    def change(self, action, **payload):
        return self.desk.mutate({'version': self.desk.private['version'], 'action': action, **payload})

    def test_collection_assignment_keeps_bytes_and_paths(self):
        before = self.desk.path(self.sha).read_bytes()
        self.change('collection_assign', id='lichen', assets=[self.sha])
        self.assertEqual(self.desk.public['collections'][0]['assets'], [self.sha])
        self.assertEqual(self.desk.path(self.sha).read_bytes(), before)
        self.assertNotIn('Archive', self.desk.path(self.sha).parts)

    def test_archive_moves_original_and_undo_survives_restart(self):
        before = self.desk.path(self.sha); raw = before.read_bytes()
        self.change('archive', assets=[self.sha])
        self.assertFalse(before.exists()); self.assertIn('Archive', self.desk.path(self.sha).parts)
        self.assertEqual(self.desk.path(self.sha).read_bytes(), raw)
        self.desk = review_desk.Desk(self.root, self.manifest)
        self.change('undo'); self.assertEqual(before.read_bytes(), raw)
        self.assertEqual(self.desk.public['archived'], [])

    def test_batch_moves_are_atomic_when_second_source_is_corrupt(self):
        second = self.manifest['assets'][1]['sha256']; self.desk.path(second).write_bytes(b'changed')
        before = copy.deepcopy(self.desk.public)
        with self.assertRaises(ValueError):
            self.change('archive', assets=[self.sha, second])
        self.assertEqual(self.desk.public, before); self.assertTrue(self.desk.path(self.sha).is_file())

    def test_destination_collision_never_overwrites(self):
        target = meta.safe_path(self.desk.library, meta.ARCHIVE + '/' + self.manifest['assets'][0]['resource_path'])
        target.parent.mkdir(parents=True); target.write_bytes(b'keep me')
        with self.assertRaises(ValueError): self.change('archive', assets=[self.sha])
        self.assertEqual(target.read_bytes(), b'keep me')

    def test_failed_metadata_write_rolls_back_move(self):
        original = review_desk.atomic_json
        def fail_once(path, value):
            if path == self.desk.public_path and value['archived']:
                raise OSError('simulated disk failure')
            return original(path, value)
        with patch.object(review_desk, 'atomic_json', side_effect=fail_once):
            with self.assertRaises(OSError): self.change('archive', assets=[self.sha])
        self.assertEqual(self.desk.public['archived'], []); self.assertEqual(meta.digest(self.desk.path(self.sha)), self.sha)
        self.assertFalse(self.desk.journal.exists())

    def test_partial_crash_transaction_recovers_before_startup_validation(self):
        before = copy.deepcopy(self.desk.public); after = copy.deepcopy(before); after['archived'] = [self.sha]
        review_desk.atomic_json(self.desk.journal, {'before': before, 'after': after, 'private_before': self.desk.private})
        source, target = list(self.desk.moves(before, after))[0]
        target.parent.mkdir(parents=True); source.rename(target)
        review_desk.atomic_json(self.desk.public_path, after)
        restarted = review_desk.Desk(self.root, self.manifest)
        self.assertEqual(restarted.public, before); self.assertTrue(source.exists()); self.assertFalse(target.exists())

    def test_stale_tab_and_external_edits_rejected(self):
        old = self.desk.private['version']; self.change('note', id=self.sha, text='private')
        with self.assertRaises(ValueError): self.desk.mutate({'action': 'archive', 'assets': [self.sha], 'version': old})
        changed = copy.deepcopy(self.desk.public); changed['revision'] += 1
        review_desk.atomic_json(self.desk.public_path, changed)
        with self.assertRaises(ValueError): self.change('archive', assets=[self.sha])

    def test_notes_private_and_original_manifest_untouched(self):
        manifest_before = (self.desk.library / 'manifest.json').read_bytes()
        self.change('note', id=self.sha, text='PRIVATE SENTINEL do not publish')
        self.change('detail_save', title='Lichen detail', asset_sha256=self.sha, rect=[.1, .2, .5, .8])
        self.assertNotIn('PRIVATE SENTINEL', self.desk.public_path.read_text())
        self.assertIn('PRIVATE SENTINEL', self.desk.private_path.read_text())
        self.assertEqual((self.desk.library / 'manifest.json').read_bytes(), manifest_before)
        pages = organization_pages(self.manifest, self.desk.public)
        self.assertNotIn('PRIVATE SENTINEL', ''.join(pages.values()))
        self.assertIn('Do not inherit cap height', pages['gallery/collections.html'])
        self.assertEqual(len(list(self.desk.library.rglob('*.png'))), 2)

    def test_bad_region_and_unknown_public_fields_rejected(self):
        for rect in ([.8, .2, .3, .5], [0, 0, float('nan'), 1], [0, 0, 2, 1], [0, 0, True, 1]):
            with self.assertRaises(ValueError): self.change('detail_save', title='detail', asset_sha256=self.sha, rect=rect)
        bad = copy.deepcopy(self.desk.public); bad['notes'] = {}
        with self.assertRaises(ValueError): meta.validate_metadata(bad, self.manifest)
        self.assertEqual(self.desk.private['version'], 0)

    def test_paths_and_symlinks_cannot_escape(self):
        for path in ('../outside', '/outside', 'resources/../outside', 'C:/outside', 'x\\y'):
            with self.assertRaises(ValueError): meta.safe_path(self.root, path)
        (self.root / 'shortcut').symlink_to(self.root / 'data', target_is_directory=True)
        with self.assertRaises(ValueError): meta.safe_path(self.root, 'shortcut/review-desk.json')

    def test_archive_public_links_and_scopes_work(self):
        self.change('archive', assets=[self.sha])
        pages = {**gallery_pages(self.manifest, self.desk.public), **organization_pages(self.manifest, self.desk.public)}
        self.assertNotIn('id="R08"', pages['gallery/index.html'])
        self.assertIn('id="R08"', pages['gallery/archive.html'])
        self.assertIn('Do not inherit cap height', pages['gallery/archive.html'])
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            for name in build_site.PUBLIC_PAGES + build_site.PUBLIC_METADATA:
                path = self.desk.library / name
                if not path.exists(): path.write_text('test', encoding='utf-8')
            build_site.publish_library(self.desk.library, output, self.manifest, self.desk.public)
            published = output / 'resources/character-library'
            self.assertEqual(meta.digest(published / self.manifest['assets'][0]['resource_path']), self.sha)
            self.assertEqual(meta.digest(published / meta.asset_relative(self.manifest['assets'][0], self.desk.public)), self.sha)
            self.assertFalse(any('.review-desk' in str(p) for p in output.rglob('*')))

    def test_regenerated_catalog_uses_physical_archive_location(self):
        for name in ('Index.md', 'Asset-Catalog.md', 'Experiments.md'):
            (self.desk.library / name).write_text('initial', encoding='utf-8')
        self.change('archive', assets=[self.sha])
        self.assertIn('Archive/ReviewDesk/resources/', (self.desk.library / 'Index.md').read_text())

    def test_public_collections_escape_titles_keep_experiments_and_unique_ids(self):
        from validate_site import Page
        self.change('detail_save', title='<script>not executable</script>', asset_sha256=self.sha, rect=[0, 0, .5, .5])
        identity = self.desk.public['details'][0]['id']
        self.change('collection_assign', id='lichen', assets=[self.sha], details=[identity])
        self.change('collection_create', name='Another feature')
        second = self.desk.public['collections'][1]['id']
        self.change('collection_assign', id=second, assets=[self.sha], details=[identity])
        body = organization_pages(self.manifest, self.desk.public)['gallery/collections.html']
        self.assertIn('&lt;script&gt;', body); self.assertNotIn('<script>not executable', body)
        page = Page(body); self.assertEqual(len(page.ids), len(set(page.ids)))
        experimental_sha = self.manifest['assets'][1]['sha256']
        self.change('detail_save', title='membrane detail', asset_sha256=experimental_sha, rect=[0, 0, .5, .5])
        body = organization_pages(self.manifest, self.desk.public)['gallery/collections.html']
        self.assertIn('Experimental parent — not baseline canon', body)

    def test_note_and_detail_delete_can_be_undone(self):
        self.change('detail_save', title='detail', asset_sha256=self.sha, rect=[0, 0, .5, .5])
        identity = self.desk.public['details'][0]['id']
        self.change('note', id=identity, text='local')
        self.change('collection_assign', id='lichen', details=[identity])
        self.change('detail_delete', id=identity); self.change('undo')
        self.assertEqual(self.desk.public['collections'][0]['details'], [identity])
        self.assertEqual(self.desk.private['notes'][identity], 'local')

    def test_server_security_and_image_endpoint(self):
        server = HTTPServer(('127.0.0.1', 0), review_desk.Handler)
        server.desk = self.desk; server.token = 'test-token'
        worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        def request(method, path, payload=None, headers=None):
            connection = HTTPConnection('127.0.0.1', server.server_port)
            connection.request(method, path, body=json.dumps(payload) if payload else None, headers=headers or {})
            response = connection.getresponse(); result = (response.status, response.read()); connection.close(); return result
        status, body = request('GET', '/api/state'); self.assertEqual(status, 200); self.assertIn(b'test-token', body)
        self.assertEqual(request('GET', '/image/' + self.sha)[1], self.desk.path(self.sha).read_bytes())
        payload = {'version': 0, 'action': 'archive', 'assets': [self.sha]}
        self.assertEqual(request('POST', '/api/change', payload)[0], 400)
        headers = {'Content-Type': 'application/json', 'X-Review-Token': 'test-token', 'Origin': 'https://untrusted.example'}
        self.assertEqual(request('POST', '/api/change', payload, headers)[0], 400)
        headers['Origin'] = f'http://127.0.0.1:{server.server_port}'
        self.assertEqual(request('POST', '/api/change', payload, headers)[0], 200)
        self.assertEqual(request('GET', '/api/state', headers={'Host': 'untrusted.example'})[0], 400)
        self.assertEqual(request('GET', '/.review-desk/local.json')[0], 404)
        self.assertEqual(request('GET', '/image/../../data/review-desk.json')[0], 400)

    def test_duplicate_running_instance_rejected(self):
        lock = review_desk.RepoLock(self.root)
        try:
            with self.assertRaises(ValueError): review_desk.RepoLock(self.root)
        finally:
            lock.close()
        second = review_desk.RepoLock(self.root); second.close()

    @unittest.skipUnless(shutil.which('node'), 'Node required for UI regression tests')
    def test_review_desk_javascript(self):
        subprocess.run(['node', str(Path(__file__).with_name('test_review_desk_ui.js'))], check=True)


if __name__ == '__main__':
    unittest.main()
