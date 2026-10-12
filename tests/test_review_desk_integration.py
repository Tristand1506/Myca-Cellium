"""Opt-in full-corpus test. Copies the library before any organization changes."""
import json
import os
from pathlib import Path
import shutil
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_site
import resource_library
import review_desk
import review_metadata as meta
import validate_site


@unittest.skipUnless(os.environ.get('MYCA_FULL_STORE_TEST') == '1', 'Set MYCA_FULL_STORE_TEST=1 for full-corpus QA')
class FullStoreTests(unittest.TestCase):
    def test_archive_details_publication_privacy_and_restarted_undo(self):
        source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('resources', 'docs', 'data', 'web', 'automation'):
                shutil.copytree(source / name, root / name)
            (root / '.gitignore').write_text('.review-desk/\n_site/\n', encoding='utf-8')
            subprocess.run(['git', 'init', '--quiet', str(root)], check=True)
            subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
            library = root / 'resources/character-library'
            snapshot = {name: (library / name).read_bytes() for name in ('manifest.json', 'SHA256SUMS')}
            with patch.object(resource_library, 'ROOT', root), patch.object(resource_library, 'LIBRARY', library):
                manifest = resource_library.load_manifest(); desk = review_desk.Desk(root, manifest)
                sha = next(r for r in manifest['references'] if r['reference_id'] == 'R08')['asset_sha256'][0]
                def change(action, **values):
                    return desk.mutate({'action': action, 'version': desk.private['version'], **values})
                change('note', id=sha, text='PRIVATE QA SENTINEL')
                change('detail_save', title='Lichen QA region', asset_sha256=sha, rect=[.1, .1, .5, .5])
                change('collection_assign', id='lichen', assets=[sha], details=[desk.public['details'][0]['id']])
                build_site.build(root=root, out=root / '_site'); validate_site.validate(root=root, out=root / '_site')
                self.assertIn('Lichen QA region', (root / '_site/gallery/collections.html').read_text())
                renamed = next(a for a in manifest['assets'] if any(
                    ':' in alias and alias.replace(':', ' -') == a['stored_filename']
                    for alias in a['filename_aliases']))
                renamed_sha = renamed['sha256']; renamed_bytes = desk.path(renamed_sha).read_bytes()
                self.assertNotIn(':', desk.path(renamed_sha).name)
                change('archive', assets=[sha, renamed_sha])
                self.assertNotIn(':', desk.path(renamed_sha).name)
                self.assertEqual(desk.path(renamed_sha).read_bytes(), renamed_bytes)
                resource_library.validate(manifest)
                build_site.build(root=root, out=root / '_site'); validate_site.validate(root=root, out=root / '_site')
                for path in (root / '_site').rglob('*'):
                    if path.is_file() and path.suffix in ('.md', '.html', '.json', '.js'):
                        self.assertNotIn('PRIVATE QA SENTINEL', path.read_text(encoding='utf-8-sig'))
                self.assertEqual({name: (library / name).read_bytes() for name in snapshot}, snapshot)
                self.assertIn('id="R08"', (root / '_site/gallery/archive.html').read_text())
                desk = review_desk.Desk(root, manifest); change('undo')
                self.assertEqual(desk.public['archived'], [])
                self.assertEqual(desk.path(renamed_sha).read_bytes(), renamed_bytes)
                resource_library.validate(manifest, images=True)


if __name__ == '__main__':
    unittest.main()
