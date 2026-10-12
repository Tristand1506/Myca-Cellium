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

    def test_boolean_request_version_is_rejected(self):
        self.change('annotation_save',record=self.annotation())
        with self.assertRaisesRegex(ValueError,'Stale tab'):
            self.desk.mutate({'version':True,'action':'annotation_save','record':self.annotation()})

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

    def comparison(self, **values):
        return {'name':'PRIVATE COMPARISON SENTINEL','items':[self.sha,self.second],
                'transforms':[{'zoom':1,'pan':[0,0],'alignment':{'offset':[0,0],'scale':1,'rotation':0}}
                              for _ in range(2)],
                'synchronized':False,'mode':'side-by-side','opacity':.5,'split':.5, **values}

    def test_comparison_sessions_validate_restore_undo_and_region_cleanup(self):
        self.change('detail_save',title='detail',asset_sha256=self.sha,rect=[.1,.1,.6,.6])
        region = self.desk.public['details'][0]['id']
        record = self.comparison(items=[self.sha,region])
        record['transforms'][1].update(zoom=2,pan=[.2,-.1])
        record['transforms'][1]['alignment'].update(offset=[.1,.2],scale=.8,rotation=12)
        self.change('comparison_save',record=record)
        saved = copy.deepcopy(self.desk.state()['workspace']['comparisons'][0])
        self.desk = review_desk.Desk(self.root,self.manifest)
        self.assertEqual(self.desk.state()['workspace']['comparisons'][0],saved)
        for values in [{'items':[self.sha]},{'items':[self.sha]*2},{'items':[self.sha,[]]},
                       {'opacity':float('inf')},{'mode':'canon'},{'synchronized':1},
                       {'transforms':[]},{'split':-1}]:
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    self.change('comparison_save',record=self.comparison(**values))
        self.change('detail_delete',id=region)
        self.assertEqual(self.desk.state()['workspace']['comparisons'],[])
        self.change('undo');self.assertEqual(self.desk.state()['workspace']['comparisons'][0],saved)
        self.change('comparison_delete',id=saved['id']);self.change('undo')
        self.assertEqual(self.desk.state()['workspace']['comparisons'][0],saved)
        self.assertNotIn('PRIVATE COMPARISON SENTINEL',json.dumps(self.desk.public))

    def iteration(self, **values):
        return {'asset_sha256':self.sha,'title':'Source study','relationship':'source','parents':[],
                'features':['lichen'],'corrections':'PRIVATE CORRECTION SENTINEL',
                'prompt':'PRIVATE PROMPT SENTINEL','outcome':'unreviewed',**values}

    def test_iteration_branches_cycle_prevention_invalid_assets_and_restarted_undo(self):
        self.change('iteration_save',record=self.iteration())
        source = copy.deepcopy(self.desk.state()['workspace']['iterations'][0])
        self.change('iteration_save',record=self.iteration(title='Revision',relationship='revision',parents=[source['id']]))
        revision = copy.deepcopy(self.desk.state()['workspace']['iterations'][1])
        self.change('iteration_save',record=self.iteration(title='Alternate',relationship='alternative',parents=[source['id']]))
        alternative = copy.deepcopy(self.desk.state()['workspace']['iterations'][2])
        for record in [self.iteration(asset_sha256='R08'),self.iteration(asset_sha256=[]),
                       self.iteration(relationship='revision',parents=['missing']),
                       self.iteration(relationship='revision'),
                       {**source,'relationship':'revision','parents':[revision['id']]},
                       {**revision,'parents':[revision['id']]},
                       self.iteration(outcome='canon')]:
            with self.subTest(record=record):
                before = copy.deepcopy(self.desk.private)
                with self.assertRaises(ValueError):
                    self.change('iteration_save',record=record)
                self.assertEqual(before,self.desk.private)
        with self.assertRaisesRegex(ValueError,'child relationships'):
            self.change('iteration_delete',id=source['id'])
        self.desk=review_desk.Desk(self.root,self.manifest)
        self.change('iteration_delete',id=alternative['id']);self.change('undo')
        self.assertEqual(self.desk.state()['workspace']['iterations'][2],alternative)
        self.assertEqual(self.desk.public_path.read_bytes(),self.public_bytes)
        self.assertNotIn('PRIVATE PROMPT SENTINEL',json.dumps(self.desk.public))

    def review(self, **values):
        return {'target':self.sha,'workflow_status':'needs-refinement','feature':'lichen',
                'severity':'major','family':'none','candidate':True,
                'nomination_reason':'PRIVATE NOMINATION SENTINEL',**values}

    def test_review_queue_nomination_never_changes_public_or_canonical_status(self):
        manifest_before=copy.deepcopy(self.manifest)
        self.change('annotation_save',record=self.annotation())
        self.change('review_save',record=self.review())
        row=next(r for r in self.desk.state()['review_queue'] if r['target']==self.sha)
        self.assertTrue(row['candidate']);self.assertTrue(row['needs_refinement'])
        self.assertEqual(row['unresolved_annotations'],1)
        saved=copy.deepcopy(self.desk.state()['workspace']['reviews'][0])
        for values in [{'workflow_status':'canon'},{'candidate':'approved'},{'target':'R08'},
                       {'feature':'unknown'},{'family':'canon'},{'canon_status':'canon'}]:
            with self.assertRaises(ValueError):
                self.change('review_save',record=self.review(**values))
        with self.assertRaisesRegex(ValueError,'Duplicate review target'):
            self.change('review_save',record=self.review())
        self.change('review_save',record={**saved,'workflow_status':'completed'})
        row=next(r for r in self.desk.state()['review_queue'] if r['target']==self.sha)
        self.assertEqual(row['workflow_status'],'completed')
        self.assertEqual(row['unresolved_annotations'],1)  # Completion never silently resolves marks.
        self.change('archive',assets=[self.sha])
        row=next(r for r in self.desk.state()['review_queue'] if r['target']==self.sha)
        self.assertTrue(row['archived']);self.assertTrue(row['candidate'])
        self.change('undo')
        self.desk=review_desk.Desk(self.root,self.manifest)
        self.change('review_delete',id=saved['id']);self.change('undo')
        self.assertEqual(self.desk.state()['workspace']['reviews'][0]['candidate'],True)
        self.assertEqual(self.manifest,manifest_before)
        self.assertEqual(self.desk.public,meta.default_metadata()|{'collections':[{'id':'lichen','name':'Lichen','assets':[],'details':[]}],'revision':2})
        self.assertNotIn('PRIVATE NOMINATION SENTINEL',json.dumps(self.desk.public))

    def test_region_review_cleanup_and_experimental_family_membership_are_reversible(self):
        self.change('collection_create',name='Shelf fungus')
        collection=copy.deepcopy(self.desk.public['collections'][-1])
        # Use a documented family ID in a fixture, without editing the real collection file.
        public=copy.deepcopy(self.desk.public);public['collections'][-1]['id']='membrane-shelf-fungus'
        self.desk.commit(public,copy.deepcopy(self.desk.private))
        self.change('collection_assign',id='membrane-shelf-fungus',assets=[self.second])
        row=next(r for r in self.desk.state()['review_queue'] if r['target']==self.second)
        self.assertIn('shelf-fungus',row['families'])
        self.change('detail_save',title='review region',asset_sha256=self.sha,rect=[.1,.1,.6,.6])
        region=self.desk.public['details'][0]['id']
        self.change('review_save',record=self.review(target=region))
        self.change('detail_delete',id=region)
        self.assertFalse(any(r['target']==region for r in self.desk.state()['workspace']['reviews']))
        self.change('undo')
        self.assertTrue(any(r['target']==region for r in self.desk.state()['workspace']['reviews']))

    def test_all_private_workspace_records_remain_excluded_from_publication(self):
        self.change('annotation_save',record=self.annotation())
        self.change('comparison_save',record=self.comparison())
        self.change('iteration_save',record=self.iteration())
        self.change('review_save',record=self.review())
        for name in build_site.PUBLIC_PAGES + build_site.PUBLIC_METADATA:
            path=self.desk.library/name
            if not path.exists():
                path.write_text('Synthetic public envelope',encoding='utf-8')
        output=self.root/'public-output'
        build_site.publish_library(self.desk.library,output,self.manifest,self.desk.public)
        self.assertFalse(any('.review-desk' in str(p) for p in output.rglob('*')))
        for path in output.rglob('*'):
            if path.is_file():
                raw=path.read_bytes()
                for sentinel in ('PRIVATE ANNOTATION','PRIVATE COMPARISON','PRIVATE PROMPT','PRIVATE NOMINATION'):
                    self.assertNotIn(sentinel.encode(),raw)

    def test_current_registered_artwork_bytes_identifiers_and_archives_are_intact(self):
        from test_review_desk import resource_library
        manifest=resource_library.load_manifest()
        resource_library.validate(manifest)  # Read-only full-corpus SHA/navigation/privacy validation.
        ids={r['reference_id'] for r in manifest['references']}
        self.assertEqual(ids,{f'R{i:02d}' for i in range(1,35)}|{f'C{i:02d}' for i in range(1,16)})

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
            rows = b''.join(bytes([0]) + bytes([80+index*40,130,100])*600 for _ in range(900))
            raw = bytes([137,80,78,71,13,10,26,10]) + chunk(b'IHDR',header) + chunk(b'IDAT',zlib.compress(rows)) + chunk(b'IEND',b'')
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
        browser.evaluate(f'selection=new Set([{json.dumps(self.sha)},{json.dumps(self.second)}]); openCompare()')
        browser.wait('compareViews.length===2 && compareViews.every(p=>p.image.complete)')
        browser.evaluate('zoomComparison(0,2)')
        self.assertEqual(browser.evaluate('compareDraft.transforms.map(t=>t.zoom)'),[2,1])
        browser.evaluate('compareDraft.synchronized=true;zoomComparison(0,1.5)')
        self.assertEqual(browser.evaluate('compareDraft.transforms.map(t=>t.zoom)'),[3,1.5])
        browser.evaluate('compareDraft.transforms[1].alignment={offset:[.1,-.1],scale:.9,rotation:12};'
                         'compareDraft.mode="overlay";compareDraft.opacity=.3;applyComparison()')
        self.assertEqual(browser.evaluate('compareViews[1].viewport.style.opacity'),'0.3')
        browser.evaluate('compareDraft.mode="slider";compareDraft.split=.25;applyComparison()')
        self.assertIn('75%',browser.evaluate('compareViews[1].viewport.style.clipPath'))
        browser.evaluate('document.getElementById("compare-name").value="Saved browser comparison";'
                         'document.getElementById("compare-save").click()')
        browser.wait('compareSessions().length===1')
        expected=browser.evaluate('compareSessions()[0]')
        browser.evaluate('compareDraft.transforms[0].zoom=1;openAdvancedCompare(compareSessions()[0])')
        self.assertEqual(browser.evaluate('compareDraft'),expected)

        browser.evaluate('document.getElementById("comparison").close()')
        self.assertEqual(self.desk.public_path.read_bytes(),self.public_bytes)
        browser.evaluate(f'mutate("detail_save",{{title:"Browser linked region",asset_sha256:{json.dumps(self.sha)},rect:[.1,.2,.6,.7]}})')
        browser.evaluate(f'mutate("detail_save",{{title:"Second region",asset_sha256:{json.dumps(self.second)},rect:[.2,.1,.8,.8]}})')
        public_after_regions=self.desk.public_path.read_bytes()
        browser.evaluate('selection=new Set([state.assets[0].sha256,state.assets[1].sha256,...state.public.details.map(d=>d.id)]);openCompare()')
        browser.wait('compareViews.length===4 && compareViews.every(p=>p.image.complete)')
        self.assertEqual(browser.evaluate('compareViews.length'),4)
        self.assertTrue(browser.evaluate('document.querySelector("#compare-mode option[value=overlay]").disabled'))
        self.assertFalse(browser.evaluate('document.documentElement.scrollWidth > innerWidth'))
        browser.evaluate('document.getElementById("comparison").close()')
        browser.evaluate('openViewer(state.public.details[0].id)')
        browser.wait('document.getElementById("image-stage").dataset.focused==="true"')
        browser.evaluate('document.getElementById("mark-tool").value="pin";beginMark()')
        browser.drag('#full-image',[.3,.3],[.3,.3])
        browser.evaluate('document.getElementById("save-mark").click()')
        browser.wait('marks().length===6 && !markDirty')
        regionMark=browser.evaluate('marks().at(-1)')
        self.assertAlmostEqual(regionMark['points'][0][0],.3,places=2)
        self.assertAlmostEqual(regionMark['points'][0][1],.3,places=2)
        browser.evaluate('focusDetail(true)')
        self.assertEqual(browser.evaluate('marks().at(-1).points'),regionMark['points'])
        browser.evaluate('closeViewer()')



        browser.evaluate(f'openHistory({json.dumps(self.sha)})')
        browser.evaluate('document.getElementById("iteration-title").value="Browser source";'
                         'document.getElementById("iteration-features").options[0].selected=true;'
                         'document.getElementById("iteration-save").click()')
        browser.wait('iterations().length===1')
        browser.evaluate('iterationFormDirty=false;editIteration();'
                         'document.getElementById("iteration-title").value="Browser revision";'
                         'document.getElementById("iteration-relationship").value="revision";'
                         'document.getElementById("iteration-parents").options[0].selected=true;'
                         'document.getElementById("iteration-save").click()')
        browser.wait('iterations().length===2')
        self.assertEqual(browser.evaluate('document.querySelectorAll(".iteration-node").length'),2)
        self.assertEqual(browser.evaluate('document.querySelectorAll(".iteration-edges > path").length'),1)
        browser.evaluate('document.getElementById("history-dialog").close()')

        browser.evaluate(f'openReviewQueue({json.dumps(self.sha)})')
        browser.evaluate('document.getElementById("review-candidate").checked=true;'
                         'document.getElementById("review-status").value="needs-refinement";'
                         'document.getElementById("review-feature").value="lichen";'
                         'document.getElementById("review-severity").value="major";'
                         'document.getElementById("review-family").value="shelf-fungus";'
                         'document.getElementById("review-reason").value="Candidate only";'
                         'document.getElementById("review-save").click()')
        browser.wait('reviewRecords().length===1 && !reviewDirty')
        browser.evaluate('document.getElementById("queue-lane").value="candidates";'
                         'document.getElementById("queue-feature").value="lichen";'
                         'document.getElementById("queue-severity").value="major";'
                         'document.getElementById("queue-family").value="shelf-fungus";renderReviewQueue()')
        self.assertEqual(browser.evaluate('document.querySelectorAll(".queue-card").length'),1)
        self.assertIn('no canon approval',browser.evaluate('document.getElementById("queue-results").textContent'))
        browser.evaluate('document.getElementById("queue-status").value="completed";renderReviewQueue()')
        self.assertEqual(browser.evaluate('document.querySelectorAll(".queue-card").length'),0)
        browser.evaluate('document.getElementById("queue-status").value="";document.getElementById("queue-dialog").close()')
        self.assertEqual(browser.evaluate('browserErrors'),[])
        browser.call('Page.reload')


        browser.wait('typeof state !== "undefined" && state?.workspace?.annotations.length===6')
        self.assertEqual(self.desk.public_path.read_bytes(), public_after_regions)


if __name__ == '__main__':
    unittest.main()
