"""v0.3 private-store and real-browser regression; isolated original artwork."""
import copy
from http.server import HTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from test_review_desk import fixture, review_desk, meta, build_site
import review_workspace as workspace
from browser_cdp import Browser, browser_path


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.manifest = fixture(self.root)
        self.desk = review_desk.Desk(self.root, self.manifest)
        self.sha = self.manifest['assets'][0]['sha256']
        self.second = self.manifest['assets'][1]['sha256']
        self.public_bytes = self.desk.public_path.read_bytes()

    def change(self, action, **payload):
        return self.desk.mutate({'version': self.desk.private['version'], 'action': action, **payload})

    def annotation(self, **values):
        return {'target': self.sha, 'kind': 'rectangle', 'points': [[.1,.2],[.7,.8]],
                'comment': 'PRIVATE ANNOTATION SENTINEL', 'feature': 'lichen',
                'severity': 'major', 'status': 'open', **values}

    def test_all_marks_edit_delete_restart_and_undo_keep_originals_and_public_bytes(self):
        raw = self.desk.path(self.sha).read_bytes()
        for kind in sorted(workspace.KINDS):
            points = [[.2,.3]] if kind == 'pin' else [[.1,.2],[.7,.8]]
            self.change('annotation_save', record=self.annotation(kind=kind, points=points))
        self.assertEqual(len(self.desk.state()['workspace']['annotations']), 5)
        self.assertEqual(self.desk.public_path.read_bytes(), self.public_bytes)
        self.assertEqual(self.desk.path(self.sha).read_bytes(), raw)
        record = copy.deepcopy(self.desk.private['workspace']['annotations'][0])
        record.update(comment='edited', status='resolved')
        self.change('annotation_save', record=record)
        self.desk = review_desk.Desk(self.root, self.manifest)
        self.assertEqual(self.desk.state()['workspace']['annotations'][0]['comment'], 'edited')
        self.change('annotation_delete', id=record['id']); self.change('undo')
        self.assertEqual(self.desk.state()['workspace']['annotations'][0], record)

    def test_bad_geometry_targets_enums_and_unknown_fields_are_atomic(self):
        invalid = [
            {'target':'R08'}, {'target':[]}, {'points':[[float('nan'),0],[1,1]]},
            {'points':[[-.01,0],[1,1]]}, {'points':[[0,0],[0,1]]},
            {'points':[[True,0],[1,1]]}, {'points':[[0,0]]},
            {'kind':'arrow','points':[[0,0],[0,0]]}, {'kind':'pin','points':[[0,0],[1,1]]},
            {'severity':'approved'}, {'status':'canon'}, {'feature':'invented'}, {'canon':'canon'}]
        for values in invalid:
            with self.subTest(values=values):
                before = copy.deepcopy(self.desk.private)
                with self.assertRaises(ValueError):
                    self.change('annotation_save', record=self.annotation(**values))
                self.assertEqual(self.desk.private, before)
        self.assertEqual(self.desk.public_path.read_bytes(), self.public_bytes)

    def test_old_private_state_and_undo_entries_remain_readable(self):
        self.change('note', id=self.sha, text='legacy note')
        private = copy.deepcopy(self.desk.private)
        private.pop('workspace')
        for entry in private['history']:
            entry.pop('workspace', None)
        review_desk.atomic_json(self.desk.private_path, private)
        self.desk = review_desk.Desk(self.root, self.manifest)
        self.change('annotation_save', record=self.annotation())
        self.change('undo')
        self.assertEqual(self.desk.state()['workspace'], workspace.empty())
        self.assertEqual(self.desk.private['notes'][self.sha], 'legacy note')
        self.change('undo'); self.assertEqual(self.desk.private['notes'], {})

    def test_delete_region_cascades_and_undo_restores_marks(self):
        self.change('detail_save', title='region', asset_sha256=self.sha, rect=[.1,.2,.6,.7])
        identity = self.desk.public['details'][0]['id']
        self.change('annotation_save', record=self.annotation(target=identity))
        self.change('detail_delete', id=identity)
        self.assertEqual(self.desk.state()['workspace']['annotations'], [])
        self.change('undo')
        self.assertEqual(self.desk.state()['workspace']['annotations'][0]['target'], identity)

    def test_private_save_failure_recovers_and_external_changes_are_rejected(self):
        self.change('annotation_save', record=self.annotation())
        original = review_desk.atomic_json
        def fail_once(path, value):
            if path == self.desk.private_path and value['version'] == 2:
                raise OSError('simulated private write failure')
            return original(path, value)
        before = copy.deepcopy(self.desk.private)
        with patch.object(review_desk, 'atomic_json', side_effect=fail_once):
            with self.assertRaises(OSError):
                self.change('annotation_save', record=self.annotation(kind='pin', points=[[.3,.3]]))
        self.assertEqual(self.desk.private, before)
        changed = copy.deepcopy(before); changed['notes'][self.sha] = 'external'
        review_desk.atomic_json(self.desk.private_path, changed)
        with self.assertRaisesRegex(ValueError, 'outside this session'):
            self.change('annotation_save', record=self.annotation())

    def test_private_records_are_outside_public_schema_and_publication(self):
        self.change('annotation_save', record=self.annotation())
        with self.assertRaises(ValueError):
            meta.validate_metadata({**self.desk.public,'annotations':[]}, self.manifest)
        self.assertNotIn('PRIVATE ANNOTATION SENTINEL', json.dumps(self.desk.public))
        self.assertNotIn('.review-desk', ' '.join(build_site.public_files(self.manifest, self.desk.public)))


@unittest.skipUnless(browser_path(), 'Chrome or Edge required (MYCA_BROWSER can select it)')
class WorkspaceBrowserTests(unittest.TestCase):
    def setUp(self):
        import hashlib
        import struct
        import zlib
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.manifest = fixture(self.root)
        def chunk(kind, data):
            return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind+data))
        for index, asset in enumerate(self.manifest['assets']):
            header = struct.pack('!IIBBBBB', 600, 900, 8, 2, 0, 0, 0)
            rows = b''.join(b'\\0' + bytes([80+index*40,130,100])*600 for _ in range(900))
            raw = b'\\x89PNG\\r\\n\\x1a\\n' + chunk(b'IHDR',header) + chunk(b'IDAT',zlib.compress(rows)) + chunk(b'IEND',b'')
            old = asset['sha256']; asset['sha256'] = hashlib.sha256(raw).hexdigest(); asset['size_bytes'] = len(raw)
            (self.root / 'resources/character-library' / asset['resource_path']).write_bytes(raw)
            for ref in self.manifest['references']:
                ref['asset_sha256'] = [asset['sha256'] if sha == old else sha for sha in ref['asset_sha256']]
        (self.root / 'resources/character-library/manifest.json').write_text(json.dumps(self.manifest),encoding='utf-8')
        self.desk = review_desk.Desk(self.root, self.manifest)
        self.sha = self.manifest['assets'][0]['sha256']; self.second = self.manifest['assets'][1]['sha256']
        self.public_bytes = self.desk.public_path.read_bytes()
    def test_browser_marks_normalize_edit_persist_and_mobile_resize(self):
        server = HTTPServer(('127.0.0.1', 0), review_desk.Handler)
        server.desk = self.desk; server.token = 'browser-token'
        worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        browser = Browser(); self.addCleanup(browser.close)
        browser.call('Emulation.setDeviceMetricsOverride', width=1280, height=900, deviceScaleFactor=1, mobile=False)
        browser.call('Page.navigate', url=f'http://127.0.0.1:{server.server_port}/')
        browser.wait('typeof state !== "undefined" && Boolean(state)')
        browser.evaluate('window.browserErrors=[]; window.addEventListener("error",e=>browserErrors.push(e.message))')
        browser.evaluate(f'openViewer({json.dumps(self.sha)})')
        browser.wait('document.getElementById("full-image").complete && document.getElementById("full-image").naturalWidth > 0')
        for kind in sorted(workspace.KINDS):
            browser.evaluate(f'document.getElementById("mark-tool").value={json.dumps(kind)}; beginMark()')
            browser.drag('#full-image', [.2,.2], [.7,.7])
            browser.wait('Boolean(markDraft)')
            browser.evaluate('document.getElementById("mark-comment").value="<script>private</script>";'
                             'markDraft.comment=document.getElementById("mark-comment").value;'
                             'document.getElementById("save-mark").click()')
            browser.wait(f'marks().length === {sorted(workspace.KINDS).index(kind)+1} && !markDirty')
        record = browser.evaluate('marks()[0]')
        browser.evaluate('markDraft=structuredClone(marks()[0]); markDraft.status="resolved"; markDirty=true; draftForm();')
        browser.evaluate('document.getElementById("save-mark").click()')
        browser.wait('marks()[0].status === "resolved" && !markDirty')
        browser.evaluate('document.getElementById("zoom").value="2";setZoom()')
        self.assertEqual(browser.evaluate('marks()[0].points'), record['points'])
        browser.call('Emulation.setDeviceMetricsOverride', width=390, height=844, deviceScaleFactor=1, mobile=True)
        browser.evaluate('document.getElementById("zoom").value="fit";setZoom()')
        self.assertEqual(browser.evaluate('marks()[0].points'), record['points'])
        self.assertFalse(browser.evaluate('document.documentElement.scrollWidth > innerWidth'))
        self.assertEqual(browser.evaluate('browserErrors'), [])
        browser.evaluate('closeViewer()')
        browser.call('Page.reload')
        browser.wait('typeof state !== "undefined" && state?.workspace?.annotations.length===5')
        self.assertEqual(self.desk.public_path.read_bytes(), self.public_bytes)


if __name__ == '__main__':
    unittest.main()
