"""DevTools startup races observed on Windows CI."""
from unittest.mock import Mock, patch
import unittest

from browser_cdp import wait_for_debug_port


class BrowserStartupTests(unittest.TestCase):
    def test_locked_and_partial_port_file_are_retried(self):
        port_file = Mock()
        port_file.read_text.side_effect = [
            PermissionError("Browser is still writing"),
            "12345",
            "12345\n/devtools/browser/session\n",
        ]
        process = Mock()
        process.poll.return_value = None
        with patch("browser_cdp.time.sleep"):
            self.assertEqual(12345, wait_for_debug_port(port_file, process))
        self.assertEqual(3, port_file.read_text.call_count)

    def test_invalid_port_file_has_a_bounded_timeout(self):
        port_file = Mock()
        port_file.read_text.return_value = "not-a-port\n/devtools/browser/session\n"
        process = Mock()
        process.poll.return_value = None
        with self.assertRaisesRegex(RuntimeError, "complete DevTools port file"):
            wait_for_debug_port(port_file, process, timeout=0)


if __name__ == "__main__":
    unittest.main()
