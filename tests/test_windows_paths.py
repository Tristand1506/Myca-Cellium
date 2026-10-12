"""Windows checkout portability is enforced on Linux CI with synthetic paths."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from windows_paths import path_errors, validate_repository


class WindowsPathsTests(unittest.TestCase):
    def test_colon_that_caused_failed_checkout_is_rejected(self):
        self.assertTrue(path_errors(['resources/hash/Myca: A Forest Mycelium Character Sheet.png']))

    def test_reserved_characters_and_controls_are_rejected(self):
        for character in '<>:"\\|?*\x00\x01\x1f':
            with self.subTest(character=repr(character)):
                self.assertTrue(path_errors(['images/file' + character + '.png']))

    def test_device_names_are_rejected_even_with_extensions(self):
        for name in ['CON', 'nul.png', 'PRN.tar.gz', 'aux', 'COM1.png', 'LPT9',
                     'COM¹.png', 'LPT².txt', 'NUL .png', 'CONIN$', 'CONOUT$']:
            with self.subTest(name=name):
                self.assertTrue(path_errors(['images/' + name]))

    def test_trailing_spaces_and_dots_are_rejected(self):
        for name in ['image.png ', 'image.png.', 'folder./image.png', 'folder /image.png']:
            self.assertTrue(path_errors([name]))

    def test_case_collisions_include_parent_directories(self):
        self.assertTrue(path_errors(['images/Myca.png', 'images/myca.png']))
        self.assertTrue(path_errors(['Images/one.png', 'images/two.png']))

    def test_safe_unicode_spaces_and_parentheses_remain_supported(self):
        self.assertFalse(path_errors(['images/Myca - Rooted in Wonder(1).png',
                                     'images/Myca’s Fungal Locomotion Field Guide.png',
                                     '.github/workflows/validate.yml', 'images/COM10.png']))

    def test_empty_absolute_and_traversal_paths_are_rejected(self):
        for path in ['', '/absolute.png', 'a//b.png', '../image.png', 'a/./b.png']:
            self.assertTrue(path_errors([path]))

    def test_component_length_is_counted_in_utf16_units(self):
        self.assertTrue(path_errors(['x' * 256]))
        self.assertTrue(path_errors(['🌿' * 128]))
        self.assertFalse(path_errors(['x' * 255]))

    def test_current_repository_has_no_windows_incompatible_paths(self):
        self.assertGreater(validate_repository(Path(__file__).resolve().parents[1]), 0)


if __name__ == '__main__':
    unittest.main()
