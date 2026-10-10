"""Regression tests use synthetic assets, without changing Myca canon or art."""
import copy
import json
from pathlib import Path
import sys
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_site
import site_gallery as gallery
from validate_site import Page, local_links


def fixture():
    assets = []
    refs = []
    for rid, classification in [('R08', ['supporting historical reference; no whole-sheet canon approval']),
                                ('C01', ['supporting historical reference; no whole-sheet canon approval']),
                                ('R32', ['experiment', 'experimental membrane design'])]:
        sha = (str(len(assets) + 1) * 64)
        assets.append({'sha256': sha, 'stored_filename': rid + ' drawing.png',
                       'resource_path': 'resources/' + sha[:16] + '/' + rid + ' drawing.png',
                       'filename_aliases': [rid + ' drawing.png'], 'size_bytes': 6,
                       'classification': classification, 'original_bytes': True})
        refs.append({'reference_id': rid, 'asset_sha256': [sha], 'status': 'recovered',
                     'design_registry': {'title': rid + ' drawing', 'status': None if rid.startswith('C') else 'Selected feature only',
                                         'approved_scope': 'Only selected lichen', 'known_defects': 'Do not inherit cap height',
                                         'crop_scope': 'Only leg proportions; inherit parent caveat'},
                     'crop': {'parent_reference_id': 'R08', 'bounds_px': [0, 0, 2, 2], 'size_px': [2, 2]}})
    for rid in ['R24', 'R25', 'R26']:
        refs.append({'reference_id': rid, 'asset_sha256': [], 'design_registry': {'title': rid + ' unavailable', 'approved_scope': 'Style only'}})
    return {'assets': assets, 'references': refs}


class GalleryTests(unittest.TestCase):
    def setUp(self):
        self.manifest = fixture()

    def test_exact_scope_and_caveat_are_visible(self):
        body = gallery.gallery_pages(self.manifest)['gallery/index.html']
        self.assertIn('Only selected lichen', body)
        self.assertIn('Do not inherit cap height', body)
        self.assertIn('Only leg proportions; inherit parent caveat', body)

    def test_experiments_are_separate_and_never_promoted(self):
        pages = gallery.gallery_pages(self.manifest)
        self.assertNotIn('id="R32"', pages['gallery/index.html'])
        self.assertIn('id="R32"', pages['gallery/experiments.html'])
        self.assertIn('remain the baseline', pages['gallery/experiments.html'])
        self.assertIn('do not create R35', pages['gallery/experiments.html'])

    def test_missing_ids_have_no_substitute_images(self):
        pages = gallery.gallery_pages(self.manifest)
        body = pages['gallery/index.html']
        for rid in ['R24', 'R25', 'R26']:
            self.assertIn('id="' + rid + '"', body)
        self.assertEqual(len(Page(body).images), 2)

    def test_null_crop_status_displays_inherited_limitations(self):
        self.assertIn('Exact detail crop; inherits parent limitations.', gallery.gallery_pages(self.manifest)['gallery/index.html'])

    def test_labels_are_escaped_and_cannot_inject_markup(self):
        self.manifest['references'][0]['design_registry']['title'] = '<script>alert(1)</script>"'
        body = gallery.gallery_pages(self.manifest)['gallery/index.html']
        self.assertNotIn('<script>', body)
        self.assertIn('&lt;script&gt;', body)

    def test_encoded_paths_preserve_spaces(self):
        self.assertIn('%20drawing.png', gallery.gallery_pages(self.manifest)['gallery/index.html'])

    def test_without_javascript_cards_and_original_links_exist(self):
        page = Page(gallery.gallery_pages(self.manifest)['gallery/index.html'])
        self.assertEqual(set(page.cards), {'R08', 'C01', 'R24', 'R25', 'R26'})
        self.assertTrue(all(a['loading'] == 'lazy' and a['alt'] for a in page.images))

    def test_input_manifest_is_not_mutated(self):
        before = copy.deepcopy(self.manifest)
        gallery.gallery_pages(self.manifest)
        self.assertEqual(before, self.manifest)

    def test_allowlist_omits_unlisted_archive_and_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            library = Path(temp) / 'library'; library.mkdir()
            output = Path(temp) / 'output'
            raw = b'original\r\nbytes\x00'
            for name in build_site.public_files(self.manifest):
                p = library / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(raw)
            (library / 'private-recovery.zip').write_bytes(b'private')
            build_site.publish_library(library, output, self.manifest)
            published = output / 'resources/character-library'
            self.assertFalse((published / 'private-recovery.zip').exists())
            self.assertEqual({p.relative_to(published).as_posix() for p in published.rglob('*') if p.is_file()}, build_site.public_files(self.manifest))
            self.assertTrue(all(p.read_bytes() == raw for p in published.rglob('*') if p.is_file()))

    def test_corrupt_manifest_stops_before_replacing_output(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'site'; output.mkdir()
            sentinel = output / 'index.html'; sentinel.write_text('previous valid build')
            with patch.object(build_site.resource_library, 'load_manifest', side_effect=ValueError('changed snapshot')):
                with self.assertRaises(ValueError):
                    build_site.build(out=output)
            self.assertEqual(sentinel.read_text(), 'previous valid build')

    def test_guide_aliases_reject_unknown_and_ambiguous_files(self):
        with self.assertRaises(ValueError):
            build_site.guide_aliases('<a href="unknown.png">', self.manifest)
        self.manifest['assets'].append(copy.deepcopy(self.manifest['assets'][0]))
        with self.assertRaises(ValueError):
            build_site.guide_aliases('<a href="R08%20drawing.png">', self.manifest)

    def test_stale_document_versions_link_to_catalog(self):
        with tempfile.TemporaryDirectory() as temp:
            rendered = build_site.rewrite_links('<a href="../missing.md">Missing</a>', 'References/Index.md', 'docs/References/Index.html', Path(temp), self.manifest, {})
            self.assertIn('../../resources/character-library/Asset-Catalog.html', rendered)

    def test_link_checker_detects_broken_and_escaping_targets(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); p = root / 'index.html'
            p.write_text('<a href="missing.html">Missing</a><img src="../private.png">')
            self.assertEqual(len(local_links(p, root)), 2)

    @unittest.skipUnless(shutil.which('node'), 'Node required for enhancement-script regression')
    def test_real_gallery_controls(self):
        subprocess.run(['node', str(Path(__file__).with_name('test_gallery_controls.js'))], check=True)


if __name__ == '__main__':
    unittest.main()
