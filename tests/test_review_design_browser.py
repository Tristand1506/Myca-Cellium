"""Real Chromium regression for the confirmed idea/checkpoint workflow."""
import base64
import os
from pathlib import Path
import copy
from http.server import HTTPServer
import json
import threading
import unittest

import test_review_workspace as existing
from test_review_workspace import review_desk
from browser_cdp import Browser, browser_path


@unittest.skipUnless(browser_path(), 'Chrome or Edge required (MYCA_BROWSER can select it)')
class DesignBrowserTests(unittest.TestCase):
    setUp = existing.WorkspaceBrowserTests.setUp

    def test_idea_lanes_multi_change_checkpoint_experiment_nomination_restore_and_reload(self):
        server = HTTPServer(('127.0.0.1', 0), review_desk.Handler)
        server.desk = self.desk; server.token = 'browser-token'
        worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        browser = Browser(); self.addCleanup(browser.close)
        browser.call('Emulation.setDeviceMetricsOverride', width=1280, height=900, deviceScaleFactor=1, mobile=False)
        browser.call('Page.navigate', url=f'http://127.0.0.1:{server.server_port}/')
        browser.wait('typeof state !== "undefined" && Boolean(state) && document.getElementById("idea-feature").options.length>0')
        browser.evaluate('window.browserErrors=[];window.addEventListener("error",e=>browserErrors.push(e.message))')
        originals = {a['sha256']: self.desk.path(a['sha256']).read_bytes() for a in self.manifest['assets']}

        def fill(id, value):
            browser.evaluate(f'document.getElementById({json.dumps(id)}).value={json.dumps(value)};'
                             f'document.getElementById({json.dumps(id)}).dispatchEvent(new Event("input",{{bubbles:true}}))')

        for name, feature, experimental in [('Legs','legs',False),('Eyes','eyes',False),('Membrane skirt','membrane',True)]:
            fill('idea-name', name); fill('idea-feature', feature)
            browser.evaluate(f'document.getElementById("idea-experimental").checked={json.dumps(experimental)};'
                             'document.getElementById("idea-create-form").requestSubmit()')
            browser.wait(f'designModel().ideas.some(i=>i.name==={json.dumps(name)})')
        idea_ids = browser.evaluate('Object.fromEntries(designModel().ideas.map(i=>[i.name,i.id]))')
        browser.evaluate('mutate("detail_save",{title:"Point crop",asset_sha256:state.assets[0].sha256,rect:[.1,.2,.6,.7]})')
        public_after_region = self.desk.public_path.read_bytes()
        for name in idea_ids:
            browser.evaluate(f'document.getElementById("design-idea").value={json.dumps(idea_ids[name])};resetDesignDraft()')
            fill('design-title', name+' source')
            if name == 'Legs':
                browser.evaluate('for(const o of document.getElementById("design-targets").options)o.selected=true')
            browser.evaluate('document.getElementById("design-form").requestSubmit()')
        self.assertEqual(browser.evaluate('designStaged.length'), 3, browser.evaluate('({toast:document.getElementById("toast").textContent,invalid:[...document.querySelectorAll("#design-form :invalid")].map(e=>({id:e.id,value:e.value})),idea:document.getElementById("design-idea").value})'))
        self.assertEqual(browser.evaluate('designModel().nodes.length'), 0)
        fill('checkpoint-name', 'Initial working choices')
        browser.evaluate('document.getElementById("checkpoint-record").click()')
        browser.wait('designModel().checkpoints.length===1 && designStaged.length===0')
        first = browser.evaluate('designModel().checkpoints[0]')
        self.assertEqual(len(first['updates']), 3)
        self.assertEqual(len(browser.evaluate('designModel().nodes.find(n=>n.idea_id==='+json.dumps(idea_ids['Legs'])+').targets')),3)
        for name in ['Legs','Eyes']:
            source = first['selections'][idea_ids[name]]
            browser.evaluate(f'inspectDesignNode({json.dumps(source)});'
                             '[...document.querySelectorAll("#design-inspector button")].find(b=>b.textContent==="Revise this iteration").click()')
            fill('design-title', name+' revision')
            browser.evaluate('document.getElementById("design-form").requestSubmit()')
        fill('checkpoint-name','Revised legs and eyes')
        browser.evaluate('document.getElementById("checkpoint-record").click()')
        browser.wait('designModel().nodes.length===5 && designStaged.length===0')
        second = browser.evaluate('designModel().checkpoints[1]')
        self.assertEqual(second['selections'][idea_ids['Membrane skirt']],first['selections'][idea_ids['Membrane skirt']])
        self.assertEqual(browser.evaluate('document.querySelectorAll(".design-node").length'),5)
        browser.wait('document.querySelectorAll(".design-edges path").length===2')
        self.assertGreater(browser.evaluate('document.querySelectorAll(".carried-label").length'),0)

        fill('branch-idea',idea_ids['Membrane skirt']);fill('branch-name','Layered petals')
        browser.evaluate('document.getElementById("branch-experimental").checked=true;document.getElementById("branch-create-form").requestSubmit()')
        browser.wait('designModel().branches.length===1')
        branch = browser.evaluate('designModel().branches[0].id')
        fill('design-title','Petal structure')
        fill('design-corrections','Living membrane; no waistband')
        browser.evaluate('document.getElementById("design-form").requestSubmit()')
        fill('checkpoint-name','Petal experiment')
        browser.evaluate('document.getElementById("checkpoint-record").click()')
        browser.wait('designModel().nodes.length===6 && designStaged.length===0')
        experiment = browser.evaluate('designModel().checkpoints[2]')
        self.assertEqual(browser.evaluate('designModel().head'),second['id'])
        node = experiment['selections'][idea_ids['Membrane skirt']]
        browser.evaluate(f'inspectDesignNode({json.dumps(node)})')
        fill('design-review-lifecycle','legacy');fill('design-review-outcome','needs-refinement')
        fill('design-review-notes','PRIVATE DESIGN BROWSER NOTES')
        fill('design-review-nomination_reason','Compare the membrane construction')
        browser.evaluate('document.getElementById("design-review-candidate").checked=true;document.getElementById("design-review-form").requestSubmit()')
        browser.wait('designModel().metadata['+json.dumps(node)+'].candidate && !designReviewDirty')
        self.assertEqual(browser.evaluate('designModel().audit.length'),1)
        browser.evaluate('openReviewQueue();document.getElementById("queue-lane").value="candidates";renderReviewQueue()')
        self.assertEqual(browser.evaluate('document.querySelectorAll(".design-queue-card").length'),1)
        browser.evaluate('document.getElementById("queue-dialog").close()')
        browser.evaluate(f'inspectDesignNode({json.dumps(node)});'
                         '[...document.querySelectorAll("#design-inspector button")].find(b=>b.textContent==="Select this version on mainline").click()')
        fill('checkpoint-name','Preferred membrane candidate')
        browser.evaluate('document.getElementById("checkpoint-record").click()')
        browser.wait('designModel().checkpoints.length===4 && Object.keys(designChoices).length===0')
        self.assertEqual(browser.evaluate('designModel().nodes.length'),6)
        self.assertEqual(browser.evaluate('designModel().checkpoints.at(-1).selections['+json.dumps(idea_ids['Membrane skirt'])+']'),node)
        self.assertTrue(browser.evaluate('designModel().branches[0].experimental'))
        self.assertEqual(browser.evaluate('designModel().checkpoints[0]'),first)
        self.assertEqual(browser.evaluate('designModel().checkpoints[2]'),experiment)

        # Combining creates one new idea iteration with explicit contributions.
        browser.evaluate('document.getElementById("design-idea").value='+json.dumps(idea_ids['Membrane skirt'])+';resetDesignDraft();document.getElementById("design-branch").value=""')
        fill('design-title','Combined membrane construction')
        browser.evaluate('for(const option of document.getElementById("design-parents").options)option.selected='+json.dumps([first['selections'][idea_ids['Membrane skirt']],node])+'.includes(option.value);document.getElementById("design-parents").dispatchEvent(new Event("change"))')
        browser.evaluate('for(const t of document.querySelectorAll("#design-contributions textarea")){t.value="Preserve the documented construction from this contributor";t.dispatchEvent(new Event("input",{bubbles:true}))}document.getElementById("design-form").requestSubmit()')
        fill('checkpoint-name','Combined membrane candidate')
        browser.evaluate('document.getElementById("checkpoint-record").click()')
        browser.wait('designModel().nodes.length===7 && designStaged.length===0')
        self.assertEqual(len(browser.evaluate('designModel().nodes.at(-1).contributions')),2)
        browser.evaluate('document.querySelectorAll(".idea-container")[2].open=false')
        browser.wait('!document.querySelectorAll(".idea-container")[2].open')
        browser.evaluate('document.querySelectorAll(".idea-container")[2].open=true')

        browser.evaluate(f'inspectCheckpoint({json.dumps(first["id"])});'
                         '[...document.querySelectorAll("#design-inspector button")].find(b=>b.textContent==="Restore these choices as a new checkpoint").click()')
        fill('checkpoint-name','Return to earlier choices')
        browser.evaluate('document.getElementById("checkpoint-record").click()')
        browser.wait('designModel().checkpoints.length===6 && designBase===null')
        self.assertEqual(browser.evaluate('designModel().checkpoints.at(-1).selections'),first['selections'])
        browser.evaluate('document.getElementById("undo").click()')
        browser.wait('designModel().checkpoints.length===5')
        if os.environ.get('MYCA_REVIEW_SCREENSHOT'):
            browser.evaluate('window.scrollTo(0,0)')
            raw=browser.call('Page.captureScreenshot',format='png',captureBeyondViewport=True,clip={'x':0,'y':0,'width':1280,'height':1600,'scale':1})
            Path(os.environ['MYCA_REVIEW_SCREENSHOT']).write_bytes(base64.b64decode(raw['data']))
        browser.call('Emulation.setDeviceMetricsOverride', width=390, height=844, deviceScaleFactor=1, mobile=True)
        self.assertFalse(browser.evaluate('document.documentElement.scrollWidth>innerWidth'))
        self.assertEqual(browser.evaluate('browserErrors'),[])
        self.assertEqual(self.desk.public_path.read_bytes(),public_after_region)
        for sha,raw in originals.items():
            self.assertEqual(self.desk.path(sha).read_bytes(),raw)
        browser.evaluate('window.rdBeforeReload=true')
        browser.call('Page.reload')
        browser.wait('typeof designModel==="function" && typeof window.rdBeforeReload==="undefined" && state?.workspace?.design?.nodes.length===7')
        self.assertEqual(browser.evaluate('designModel().metadata['+json.dumps(node)+'].notes'),'PRIVATE DESIGN BROWSER NOTES')
        self.assertEqual(browser.evaluate('designModel().checkpoints.length'),5)
