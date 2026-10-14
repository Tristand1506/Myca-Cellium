"""Include the isolated prototype in the existing repository validation suite."""
from pathlib import Path
import os
import unittest


def load_tests(loader, standard_tests, pattern):
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        os.environ['CONTENT_STUDIO_REQUIRE_BROWSER'] = '1'
    directory = Path(__file__).resolve().parents[1] / "prototypes/content-studio/tests"
    return unittest.TestLoader().discover(
        str(directory), pattern=pattern or "test*.py", top_level_dir=str(directory))
