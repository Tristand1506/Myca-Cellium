"""Windows-style Git checkout regression without weakening byte pins."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import repair_checkout_bytes as repair
import resource_library


class CheckoutBytesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'source'; self.root.mkdir()
        self.library = self.root / 'resources/character-library'; self.library.mkdir(parents=True)
        (self.root / 'docs').mkdir()
        (self.library / 'SHA256SUMS').write_bytes(b'known checksum ledger\n')
        (self.library / 'manifest.json').write_bytes(b'{\n  "schema_version": "1.0"\n}\n')
        (self.library / 'historical.md').write_bytes(b'Original CRLF\r\nKeep these bytes\r\n')
        (self.root / 'docs/guide.html').write_bytes(b'<p>Original</p>\n')
        self.git('init', '-q'); self.git('config', 'core.autocrlf', 'false')
        self.git('add', '.')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture')

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root, stderr=subprocess.PIPE)

    def checkout(self, name):
        target = Path(self.temp.name) / name
        subprocess.run(['git', 'clone', '--shared', '--no-checkout', str(self.root), str(target)], check=True, capture_output=True)
        subprocess.run(['git', '-c', 'core.autocrlf=true', '-c', 'core.eol=crlf', 'checkout', '-f', 'HEAD'], cwd=target, check=True, capture_output=True)
        return target

    def test_without_attributes_same_checksum_error_is_reproduced(self):
        target = self.checkout('converted')
        pins = {name: hashlib.sha256((self.library / name).read_bytes()).hexdigest()
                for name in ('SHA256SUMS', 'manifest.json')}
        with patch.object(resource_library, 'LIBRARY', target / 'resources/character-library'), \
             patch.object(resource_library, 'ROOT', target), patch.object(resource_library, 'EXPECTED_HASHES', pins):
            with self.assertRaisesRegex(ValueError, 'Reviewed snapshot changed: SHA256SUMS'):
                resource_library.load_manifest()
            repair.repair(target, apply=True)
            self.assertEqual(resource_library.load_manifest()['schema_version'], '1.0')

    def test_attributes_preserve_original_lf_and_crlf_bytes(self):
        attributes = (Path(__file__).resolve().parents[1] / '.gitattributes').read_bytes()
        (self.root / '.gitattributes').write_bytes(attributes)
        self.git('add', '.gitattributes')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'protect bytes')
        target = self.checkout('protected')
        for relative in ('resources/character-library/SHA256SUMS', 'resources/character-library/manifest.json',
                         'resources/character-library/historical.md', 'docs/guide.html'):
            self.assertEqual((target / relative).read_bytes(), (self.root / relative).read_bytes())

    def test_dry_run_leaves_bytes_untouched_and_other_edits_are_preserved(self):
        converted = self.library / 'SHA256SUMS'; converted.write_bytes(b'known checksum ledger\r\n')
        changed = self.library / 'manifest.json'; changed.write_bytes(b'{"actual user edit":true}\n')
        before = converted.read_bytes(); repair.repair(self.root)
        self.assertEqual(converted.read_bytes(), before)
        count, conflicts = repair.repair(self.root, apply=True)
        self.assertEqual(count, 1); self.assertIn('resources/character-library/manifest.json', conflicts)
        self.assertEqual(changed.read_bytes(), b'{"actual user edit":true}\n')
        self.assertEqual((self.library / 'historical.md').read_bytes(), b'Original CRLF\r\nKeep these bytes\r\n')

    def test_missing_files_are_not_recreated(self):
        path = self.library / 'SHA256SUMS'; path.unlink()
        repair.repair(self.root, apply=True); self.assertFalse(path.exists())

    def test_staged_changes_are_not_overwritten(self):
        path = self.library / 'SHA256SUMS'; path.write_bytes(b'edited and staged\n'); self.git('add', str(path))
        with self.assertRaisesRegex(ValueError, 'staged changes'):
            repair.repair(self.root, apply=True)
        self.assertEqual(path.read_bytes(), b'edited and staged\n')


if __name__ == '__main__':
    unittest.main()
