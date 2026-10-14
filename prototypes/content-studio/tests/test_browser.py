"""Real-browser regression checks for the standalone interface."""
import base64
import hashlib
import os
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

from browser_cdp import Browser, browser_path

APP = Path(__file__).resolve().parents[1] / "index.html"


def png(path, width, height, color):
    """Synthetic fixtures; no source artwork or image libraries."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    raw = (b"\0" + bytes(color) * width) * height
    path.write_bytes(b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class PrototypeBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not browser_path():
            if os.environ.get("CONTENT_STUDIO_REQUIRE_BROWSER") == "1":
                raise RuntimeError("A Chromium browser is required for this test run")
            raise unittest.SkipTest("Chrome, Chromium, or Edge is not installed")

    def setUp(self):
        self.b = Browser()
        self.addCleanup(self.b.close)
        self.b.call("Emulation.setDeviceMetricsOverride",
                    width=1024, height=1000, deviceScaleFactor=1, mobile=False)
        self.open()

    def open(self):
        self.b.call("Page.navigate", url=APP.as_uri())
        self.b.wait("document.getElementById('git-content-prototype')?.prototypeApps?.length===1")
        self.b.evaluate("""
        window.A=document.getElementById('git-content-prototype').prototypeApps[0];
        window.Q=s=>document.querySelector('#studio-tree '+s);
        window.click=s=>Q(s).click();
        window.input=(s,v)=>{Q(s).value=v;Q(s).dispatchEvent(new Event('input',{bubbles:true}));};
        window.change=(s,v)=>{Q(s).value=v;Q(s).dispatchEvent(new Event('change',{bubbles:true}));};
        window.fields=()=>A.state.drafts[A.activeBranch].fields;
        window.gallery=()=>fields().find(f=>f.id==='gallery');
        """)
        self.b.wait("!!Q('[data-act=\"field-rename:title\"] svg')")

    def yes(self, expression):
        self.assertTrue(self.b.evaluate(expression), expression)

    def upload(self, files):
        root = self.b.call("DOM.getDocument")["root"]["nodeId"]
        node = self.b.call("DOM.querySelector", nodeId=root,
                          selector="#studio-tree [data-id=media-upload]")["nodeId"]
        self.b.call("DOM.setFileInputFiles", nodeId=node, files=[str(p) for p in files])
        self.b.wait("!Q('[data-id=media-upload]').disabled")

    def fixtures(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        (root / "a").mkdir()
        (root / "b").mkdir()
        first, second = root / "a/sample.png", root / "b/sample.png"
        png(first, 64, 32, (50, 100, 150))
        png(second, 32, 64, (150, 100, 50))
        return first, second

    def test_field_icons_rename_order_and_recorded_history(self):
        self.yes("A.view==='Editor' && Q('[data-act=\"field-move:title:-1\"]').disabled")
        self.yes("""Array.from(Q('[data-editor-field=title] .field-actions').querySelectorAll('button'))
          .every(el=>el.textContent.trim()===''&&!!el.querySelector('svg')&&
                     !!el.title&&!!el.getAttribute('aria-label'))""")
        self.b.evaluate("""
        window.saved=JSON.stringify(A.state.nodes);
        Q('[data-act="field-rename:title"] svg').dispatchEvent(new MouseEvent('click',{bubbles:true}));
        input('[data-input=field-name]','Cancelled');
        click('[data-act=cancel]');
        """)
        self.yes("fields()[0].label==='Title' && !A.state.drafts.main.dirty")
        self.b.evaluate("""
        click('[data-act="field-rename:title"]');input('[data-input=field-name]','');
        click('[data-act=save-modal]');
        """)
        self.b.wait("!!Q('.modal-body [role=alert]')")
        self.b.evaluate("""
        input('[data-input=field-name]','Headline');click('[data-act=save-modal]');
        input('[data-field=body]','Retained draft');click('[data-act="field-move:body:-1"]');
        """)
        self.yes("""fields()[0].id==='title' && fields()[0].label==='Headline' &&
          fields()[1].id==='body' && Q('[data-field=body]').value==='Retained draft' &&
          JSON.stringify(A.state.nodes)===saved""")
        self.b.evaluate("""
        click('[data-act=record]');click('[data-act=save-modal]');
        change('[data-id=revision]','n3');
        """)
        self.yes("""!Q('[data-act^="field-rename:"]') && !Q('[data-act^="field-move:"]') &&
          Q('[data-editor-field=title] label').textContent==='Title' &&
          A.state.nodes.find(n=>n.id==='n8').fields[0].label==='Headline'""")
        self.b.evaluate("click('[data-act=edit-draft]');A.navigate('CMS')")
        self.yes("""A.state.blocks[0].field==='title' &&
          Q('[data-input=source-field]').options[0].text.includes('Headline')""")

    def test_independent_versions_fork_and_template_isolation(self):
        self.b.evaluate("""
        input('[data-field=title]','Unsaved title');change('[data-id=revision]','n2');
        click('[data-branch=coast]');change('[data-id=revision]','n4');
        click('[data-branch=main]');
        """)
        self.yes("Q('[data-id=revision]').value==='n2' && A.state.drafts.main.fields[0].value==='Unsaved title'")
        self.b.evaluate("click('[data-branch=coast]')")
        self.yes("Q('[data-id=revision]').value==='n4'")
        self.b.evaluate("""
        click('[data-branch=main]');click('[data-act=edit-draft]');
        click('[data-act=fork]');input('[data-input=name]','Title direction');
        click('[data-act=save-modal]');click('[data-act=templates]');
        Q('[data-template=title]').value='Template title';click('[data-act=save-modal]');
        """)
        self.yes("""A.state.nodes.at(-1).fields[0].value==='Unsaved title' &&
          A.state.drafts.main.fields[0].value==='Unsaved title'""")

    def test_multiple_images_bytes_order_pinned_and_recorded_output(self):
        first, second = self.fixtures()
        self.b.evaluate("""
        click('[data-act=field-add]');input('[data-input=label]','Reference images');
        input('[data-input=id]','gallery');change('[data-input=type]','gallery');
        click('[data-act=save-modal]');click('[data-act="media-pick:gallery"]');
        """)
        self.upload([first, second])
        self.b.wait("A.state.media.length===2")
        self.b.evaluate("click('[data-act=save-modal]')")
        self.b.wait("Q('.gallery-editor img[data-image-id=m1]')?.naturalWidth===64")
        url = self.b.evaluate("A.state.media[0].url")
        self.assertEqual(hashlib.sha256(base64.b64decode(url.split(",")[1])).digest(),
                         hashlib.sha256(first.read_bytes()).digest())
        self.yes("gallery().mediaIds.join(',')==='m1,m2' && A.state.nodes.length===7")
        self.b.evaluate("""
        click('[data-act="gallery-move:gallery:1:-1"]');click('[data-act=record]');
        click('[data-act=save-modal]');click('[data-act="gallery-remove:gallery:0"]');
        A.navigate('CMS');click('[data-act=section-add]');
        change('[data-input=section-type]','gallery');change('[data-input=section-mode]','dynamic');
        change('[data-input=source-field]','gallery');
        """)
        self.b.wait("Q('.bound-gallery img')?.naturalWidth===64")
        self.yes("Q('.bound-gallery').querySelectorAll('img').length===1")
        self.b.evaluate("change('[data-input=source-revision]','n8')")
        self.b.wait("Q('.bound-gallery img')?.naturalWidth===32")
        self.yes("""Array.from(Q('.bound-gallery').querySelectorAll('img'))
          .map(i=>i.dataset.imageId).join(',')==='m2,m1'""")
        self.b.evaluate("change('[data-input=source-revision]','latest');A.navigate('Preview');click('[data-act=export]')")
        html = self.b.evaluate("Q('.dialog textarea').value")
        self.assertLess(html.index('data-image-id="m2"'), html.index('data-image-id="m1"'))
        self.yes("A.state.nodes.find(n=>n.id==='n8').fields.find(f=>f.id==='gallery').mediaIds.length===2")

    def test_single_image_invalid_file_and_missing_field_export(self):
        first, _ = self.fixtures()
        bad = first.parent / "invalid.png"
        bad.write_bytes(b"Not an image")
        self.b.evaluate("click('[data-act=\"media-pick:cover\"]')")
        self.upload([first])
        self.b.wait("A.state.media.length===1")
        self.b.evaluate("click('[data-act=save-modal]');click('[data-act=\"media-pick:cover\"]')")
        self.upload([bad])
        self.b.wait("!Q('[data-id=media-error]').hidden")
        self.yes("A.state.media.length===1 && fields().find(f=>f.id==='cover').mediaId==='m1'")
        self.b.evaluate("""
        click('[data-act=cancel]');click('[data-act="remove:title"]');
        click('[data-act=record]');click('[data-act=save-modal]');A.navigate('Preview');
        """)
        self.yes("Q('[data-act=export]').disabled && Q('.warning').textContent.includes('title')")

    def test_detached_revisions_connection_and_head_alignment(self):
        self.b.evaluate("""
        click('[data-branch=short]');input('[data-field=body]','Detached refinement');
        click('[data-act=record]');click('[data-act=save-modal]');A.navigate('Timeline');
        """)
        self.b.wait("!!Q('[data-node=n8]')")
        self.b.evaluate("click('[data-node=n8]');click('[data-act=connect]');click('[data-act=save-modal]')")
        self.yes("A.state.nodes.some(n=>n.id==='n7') && A.state.nodes.some(n=>n.id==='n8')")
        self.b.evaluate("A.navigate('Timeline')")
        self.b.wait("!!Q('[data-node=n3]') && !!Q('[data-node=n5]')")
        self.yes("""(()=>{const heads=A.state.branches.map(b=>Q('[data-node="'+b.head+'"]'));
          const ys=heads.map(el=>el.getBoundingClientRect().y);
          return heads.every(Boolean)&&Math.max(...ys)-Math.min(...ys)<1;})()""")

    def test_compact_controls_touch_and_scrolled_modal(self):
        self.b.call("Emulation.setDeviceMetricsOverride",
                    width=320, height=400, deviceScaleFactor=1, mobile=False)
        self.b.wait("document.documentElement.scrollWidth<=innerWidth")
        self.b.evaluate("Q('[data-act=\"field-rename:body\"]').scrollIntoView({block:'center'})")
        scroll = self.b.evaluate("scrollY")
        self.b.evaluate("click('[data-act=\"field-rename:body\"]')")
        self.b.wait("""(()=>{const r=Q('.dialog').getBoundingClientRect();
          return r.top>=0&&r.bottom<=innerHeight&&r.left>=0&&r.right<=innerWidth;})()""")
        self.assertAlmostEqual(scroll, self.b.evaluate("scrollY"), delta=2)
        self.b.evaluate("click('[data-act=cancel]')")
        self.b.call("Emulation.setTouchEmulationEnabled", enabled=True, maxTouchPoints=5)
        self.b.call("Emulation.setDeviceMetricsOverride",
                    width=320, height=800, deviceScaleFactor=1, mobile=True)
        self.b.wait("""Array.from(Q('[data-editor-field=title] .field-actions').querySelectorAll('button'))
          .every(el=>el.getBoundingClientRect().height>=44)""")

    def test_reload_resets_prototype_session(self):
        self.b.evaluate("input('[data-field=title]','Session only');click('[data-act=record]');click('[data-act=save-modal]')")
        self.yes("A.state.nodes.length===8")
        self.open()
        self.yes("A.state.nodes.length===7 && fields()[0].value==='Places to pause' && A.state.media.length===0")


if __name__ == "__main__":
    unittest.main()
