"""Collection topics must never expand reference approvals."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import feature_references as features
import review_metadata as meta
from test_site_gallery import fixture
from validate_site import Page, local_links
import build_site


class FeatureAssignmentTests(unittest.TestCase):
    def setUp(self):
        self.manifest = fixture()
        self.extra = copy.deepcopy(self.manifest['assets'][2])
        self.extra.update(sha256='4' * 64, stored_filename='unregistered experiment.png',
                          resource_path='resources/unregistered experiment.png')
        self.manifest['assets'].append(self.extra)
        self.org = meta.default_metadata()
        self.org['revision'] = 21
        self.org['collections'] = [
            {'id': 'face-eyes', 'name': 'Renamed review topic',
             'assets': ['2' * 64], 'details': ['view-region']},
            {'id': 'membranes', 'name': 'Membrane experiments',
             'assets': ['3' * 64, '4' * 64], 'details': []},
            {'id': 'custom', 'name': 'Cap', 'assets': ['1' * 64], 'details': []},
        ]
        self.org['details'] = [
            {'id': 'view-region', 'title': 'Narrow selected region', 'asset_sha256': '1' * 64,
             'rect': [0.1, 0.2, 0.4, 0.5]}]
        self.org['archived'] = ['1' * 64]
        self.mapping = {'face-eyes': 'face-eyes', 'membranes': 'membrane-experiments'}

    def derive(self):
        return features.assignments(self.manifest, self.org, self.mapping)

    def test_topics_use_explicit_ids_never_names_or_approval_scope(self):
        result = self.derive()
        face, membrane, custom = result['collections']
        self.assertEqual(face['feature_id'], 'face-eyes')
        self.assertIsNone(custom['feature_id'])  # A collection named Cap does not opt in.
        selected = face['items'][0]['references'][0]
        self.assertEqual(selected, self.manifest['references'][1])
        self.assertIn('Only leg proportions', selected['design_registry']['crop_scope'])
        self.assertIsNone(selected['design_registry']['status'])
        self.assertIn('organizational membership only', result['interpretation'])

    def test_all_existing_references_and_crop_parents_survive(self):
        extra_ref = copy.deepcopy(self.manifest['references'][1])
        extra_ref['reference_id'] = 'C02'
        self.manifest['references'].append(extra_ref)
        item = self.derive()['collections'][0]['items'][0]
        self.assertEqual([r['reference_id'] for r in item['references']], ['C01', 'C02'])
        self.assertEqual(item['parent_references'], [self.manifest['references'][0]])

    def test_experiments_and_unregistered_art_are_not_promoted(self):
        items = self.derive()['collections'][1]['items']
        self.assertEqual(items[0]['references'][0], self.manifest['references'][2])
        self.assertEqual(items[1]['references'], [])
        self.assertEqual(items[1]['classification'], ['experiment', 'experimental membrane design'])
        body = features.feature_page(self.manifest, self.derive())
        self.assertIn('No R/C ID or feature approval assigned', body)
        self.assertIn('experimental membrane design', body)

    def test_archived_memberships_are_retained_and_labeled(self):
        result = self.derive()
        self.assertTrue(result['collections'][2]['items'][0]['archived'])
        self.assertTrue(result['collections'][0]['items'][1]['archived'])
        body = features.feature_page(self.manifest, result)
        self.assertIn('Archived; excluded from active collections', body)
        self.assertIn('0 active / 1 saved memberships', body)

    def test_detail_assigns_only_region_not_whole_parent(self):
        self.org['collections'][2]['assets'] = []
        result = self.derive()
        self.assertIn('1' * 64, result['unassigned_asset_sha256'])
        item = result['collections'][0]['items'][1]
        self.assertEqual(item['detail'], self.org['details'][0])
        self.assertEqual(item['references'][0]['reference_id'], 'R08')
        self.assertIn('No new crop or R/C ID', features.feature_page(self.manifest, result))

    def test_missing_refs_stay_reserved_without_substitute_assignments(self):
        result = self.derive()
        self.assertEqual(result['missing_reference_ids'], ['R24', 'R25', 'R26'])
        self.assertEqual(sum(len(c['items']) for c in result['collections']), 5)

    def test_inputs_and_returned_records_are_independent(self):
        before = copy.deepcopy((self.manifest, self.org, self.mapping))
        result = self.derive()
        self.assertEqual((self.manifest, self.org, self.mapping), before)
        result['collections'][0]['items'][0]['references'][0]['design_registry']['crop_scope'] = 'changed'
        self.assertEqual((self.manifest, self.org, self.mapping), before)

    def test_page_preserves_scope_and_parent_caveats_and_escapes_titles(self):
        self.org['collections'][0]['name'] = '<script>topic</script>'
        result = self.derive()
        body = features.feature_page(self.manifest, result)
        self.assertNotIn('<script>', body)
        self.assertIn('&lt;script&gt;topic&lt;/script&gt;', body)
        self.assertIn('Only leg proportions; inherit parent caveat', body)
        self.assertIn('Do not inherit cap height', body)
        self.assertIn('feature-face-eyes', Page(body).ids)
        self.assertEqual(len(Page(body).ids), len(set(Page(body).ids)))

    def test_private_fields_rejected_and_not_serialized(self):
        self.org['notes'] = {'secret': 'private'}
        with self.assertRaises(ValueError):
            self.derive()

    def test_empty_organization_reports_no_saved_assignments(self):
        self.org = meta.default_metadata()
        result = self.derive()
        self.assertEqual(result['collections'], [])
        self.assertEqual(len(result['unassigned_asset_sha256']), 4)
        self.assertIn('No saved collection assignments', features.feature_page(self.manifest, result))

    def test_invalid_mapping_stops_build_before_previous_output_is_removed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'data').mkdir()
            (root / features.CONFIG_PATH).write_text('{"schema_version":1,"approved":true}')
            out = root / '_site'; out.mkdir()
            sentinel = out / 'index.html'; sentinel.write_text('previous valid build')
            with patch.object(build_site.resource_library, 'load_manifest', return_value=self.manifest), \
                 patch.object(build_site.resource_library, 'validate'), \
                 patch.object(build_site.review_metadata, 'load_metadata', return_value=self.org):
                with self.assertRaises(ValueError):
                    build_site.build(root=root, out=out)
            self.assertEqual(sentinel.read_text(), 'previous valid build')

    def test_cross_page_collection_fragments_are_verified(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'gallery').mkdir()
            target = root / 'gallery/collections.html'
            target.write_text('<section id="collection-face-eyes"></section>')
            source = root / 'gallery/features.html'
            source.write_text('<a href="collections.html#collection-face-eyes">Open</a>')
            self.assertEqual(local_links(source, root), [])
            source.write_text('<a href="collections.html#missing">Open</a>')
            self.assertEqual(len(local_links(source, root)), 1)

    def test_mapping_rejects_unknown_topics_approval_fields_and_bad_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'data').mkdir()
            path = root / features.CONFIG_PATH
            for config in [
                {'schema_version': 1, 'collection_features': {'cap': 'canon'}},
                {'schema_version': 1, 'collection_features': {}, 'approved': True},
                {'schema_version': 1, 'collection_features': {'../cap': 'cap'}},
                {'schema_version': True, 'collection_features': {}},
            ]:
                path.write_text(json.dumps(config))
                with self.assertRaises(ValueError):
                    features.load_features(root)
            path.unlink()
            self.assertEqual(features.load_features(root), {})

    def test_mapping_keeps_stable_ids_across_renames_and_deletions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'data').mkdir()
            config = {'schema_version': 1, 'collection_features': {'cap': 'cap'}}
            (root / features.CONFIG_PATH).write_text(json.dumps(config))
            self.assertEqual(features.load_features(root), {'cap': 'cap'})


if __name__ == '__main__':
    unittest.main()
