"""Checkpoint history regressions through the same Desk interface used by the browser."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from test_review_desk import fixture, review_desk
import review_design as design


class DesignTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = fixture(self.root)
        self.desk = review_desk.Desk(self.root, self.manifest)
        self.sha = self.manifest['assets'][0]['sha256']
        self.original = self.desk.path(self.sha).read_bytes()
        self.public = self.desk.public_path.read_bytes()

    @property
    def model(self):
        return self.desk.state()['workspace'].get('design', design.empty())

    def change(self, action, **payload):
        return self.desk.mutate({'version': self.desk.private['version'], 'action': action, **payload})

    def idea(self, name='Legs', feature='legs', experimental=False):
        self.change('idea_create', record={'name': name, 'feature': feature,
                                          'family': 'none', 'experimental': experimental})
        return self.model['ideas'][-1]['id']

    def node(self, idea, title='Version one', **changes):
        return {'idea_id': idea, 'branch_id': None, 'title': title, 'targets': [],
                'prompt': 'PRIVATE DESIGN PROMPT', 'corrections': '', 'parents': [],
                'contributions': [], 'legacy_id': None, **changes}

    def record(self, *nodes, **changes):
        self.change('design_checkpoint', name='Working checkpoint', route='mainline', nodes=list(nodes),
                    selections={n['idea_id']: '$' + str(i) for i, n in enumerate(nodes)}, **changes)
        return self.model['checkpoints'][-1]

    def test_multiple_ideas_at_one_checkpoint_carry_versions_without_iteration(self):
        legs = self.idea(); eyes = self.idea('Eyes', 'eyes'); cap = self.idea('Cap', 'cap')
        first = self.record(self.node(legs), self.node(eyes), self.node(cap))
        second = self.record(self.node(legs, 'Pointed legs', parents=[first['selections'][legs]]),
                             self.node(eyes, 'Revised eyes', targets=[self.sha]))
        self.assertEqual(len(self.model['nodes']), 5)
        self.assertEqual(second['selections'][cap], first['selections'][cap])
        self.assertEqual(len(second['updates']), 2)
        self.assertEqual(self.model['checkpoints'][0], first)
        self.assertEqual(self.desk.public_path.read_bytes(), self.public)
        self.assertEqual(self.desk.path(self.sha).read_bytes(), self.original)
        self.desk = review_desk.Desk(self.root, self.manifest)
        self.change('undo')
        self.assertEqual(self.model['head'], first['id'])
        self.assertEqual(len(self.model['nodes']), 3)

    def test_experimental_context_follows_mainline_but_historical_checkpoint_does_not(self):
        legs = self.idea(); skirt = self.idea('Membrane skirt', 'membrane', True)
        first = self.record(self.node(legs), self.node(skirt))
        self.change('branch_create', record={'idea_id': skirt, 'name': 'Layered petals',
                    'experimental': True, 'parents': [], 'base': first['id']})
        branch = self.model['branches'][-1]['id']
        self.change('design_checkpoint', name='Petals', route=branch,
                    nodes=[self.node(skirt, branch_id=branch, parents=[first['selections'][skirt]])],
                    selections={skirt: '$0'})
        experiment = copy.deepcopy(self.model['checkpoints'][-1])
        revised = self.record(self.node(legs, 'Slim calves', parents=[first['selections'][legs]]))
        context = design.context(self.model, branch)
        self.assertEqual(context[legs], revised['selections'][legs])
        self.assertEqual(context[skirt], experiment['selections'][skirt])
        self.assertEqual(self.model['checkpoints'][1], experiment)
        self.assertEqual(self.model['head'], revised['id'])
        self.change('design_checkpoint', name='Adopt selected membrane', route='mainline',
                    selections={skirt: experiment['selections'][skirt]}, merge=experiment['id'])
        self.assertEqual(len(self.model['nodes']), 4)
        self.assertEqual(self.model['checkpoints'][-1]['selections'], context)
        self.assertTrue(self.model['branches'][0]['experimental'])
        self.assertEqual(self.desk.public_path.read_bytes(), self.public)

    def test_combining_requires_explicit_contributions_and_reuses_existing_selection(self):
        idea = self.idea()
        first = self.record(self.node(idea))
        source = first['selections'][idea]
        second = self.record(self.node(idea, 'Alternative', parents=[source]))
        alternate = second['selections'][idea]
        before = copy.deepcopy(self.desk.private)
        with self.assertRaisesRegex(ValueError, 'contribution'):
            self.record(self.node(idea, 'Combination', parents=[source, alternate]))
        self.assertEqual(self.desk.private, before)
        combined = self.record(self.node(idea, 'Combination', parents=[source, alternate],
                              contributions=[{'node_id': source, 'detail': 'Preserve uninterrupted tip'},
                                             {'node_id': alternate, 'detail': 'Use slimmer calves'}]))
        self.assertEqual(len(self.model['nodes']), 3)
        self.change('design_checkpoint', name='Return to version one', route='mainline', base=first['id'])
        self.assertEqual(len(self.model['nodes']), 3)
        self.assertEqual(self.model['checkpoints'][-1]['selections'][idea], source)
        self.assertIn(combined['id'], self.model['checkpoints'][-1]['parents'])

    def test_invalid_references_and_cross_idea_changes_are_atomic(self):
        idea = self.idea(); other = self.idea('Eyes', 'eyes')
        first = self.record(self.node(idea))
        self.change('branch_create', record={'idea_id': idea, 'name': 'Alternative',
                    'experimental': False, 'parents': [], 'base': first['id']})
        branch = self.model['branches'][0]['id']
        invalid = [
            {'nodes': [self.node(idea, targets=['unknown'])], 'selections': {idea: '$0'}},
            {'nodes': [self.node(idea, targets=[True])], 'selections': {idea: '$0'}},
            {'nodes': [self.node(idea, parents=['unknown'])], 'selections': {idea: '$0'}},
            {'nodes': [self.node(other, parents=[first['selections'][idea]])], 'selections': {other: '$0'}},
            {'nodes': [self.node(idea), self.node(idea)], 'selections': {idea: '$0'}},
            {'nodes': [self.node(idea)], 'selections': {}},
            {'nodes': [], 'selections': {other: first['selections'][idea]}},
            {'nodes': [], 'selections': {idea: '$-1'}},
            {'nodes': [self.node(other, branch_id=branch)], 'selections': {other: '$0'}, 'route': branch},
            {'nodes': [{**self.node(idea), 'canon': True}], 'selections': {idea: '$0'}},
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                before = copy.deepcopy(self.desk.private)
                with self.assertRaises(ValueError):
                    self.change('design_checkpoint', name='Invalid', **payload)
                self.assertEqual(self.desk.private, before)
        self.assertEqual(self.desk.public_path.read_bytes(), self.public)

    def test_immutable_content_and_audited_labels_nomination_and_undo(self):
        idea = self.idea()
        self.record(self.node(idea, targets=[self.sha]))
        node = copy.deepcopy(self.model['nodes'][0])
        metadata = {**self.model['metadata'][node['id']], 'notes': 'PRIVATE DESIGN NOTE',
                    'lifecycle': 'legacy', 'outcome': 'reviewed', 'candidate': True,
                    'nomination_reason': 'Review pointed leg geometry only'}
        self.change('design_metadata', id=node['id'], record=metadata)
        self.assertEqual(self.model['nodes'][0], node)
        self.assertEqual(self.model['audit'][0]['after'], metadata)
        self.assertEqual(self.desk.path(self.sha).read_bytes(), self.original)
        self.desk = review_desk.Desk(self.root, self.manifest)
        with self.assertRaises(ValueError):
            self.change('design_metadata', id=node['id'], record={**metadata, 'title': 'Rewrite'})
        with self.assertRaises(ValueError):
            self.change('design_metadata', id=node['id'], record={**metadata, 'outcome': 'canon'})
        self.change('undo')
        self.assertFalse(self.model['metadata'][node['id']]['candidate'])
        self.assertEqual(self.model['audit'], [])
        self.assertNotIn('PRIVATE DESIGN', json.dumps(self.desk.public))

    def test_saved_regions_and_unassigned_ancestry_are_preserved(self):
        self.change('detail_save', title='Tip', asset_sha256=self.sha, rect=[.1,.1,.6,.6])
        region = self.desk.public['details'][0]['id']
        self.change('iteration_save', record={'asset_sha256': self.sha, 'title': 'Old source',
                    'relationship': 'source', 'parents': [], 'features': ['legs'],
                    'corrections': '', 'prompt': '', 'outcome': 'unreviewed'})
        old = copy.deepcopy(self.desk.state()['workspace']['iterations'])
        idea = self.idea()
        self.record(self.node(idea, targets=[self.sha, region], legacy_id=old[0]['id']))
        with self.assertRaisesRegex(ValueError, 'referenced by design'):
            self.change('detail_delete', id=region)
        with self.assertRaisesRegex(ValueError, 'linked to design'):
            self.change('iteration_delete', id=old[0]['id'])
        self.assertEqual(self.desk.state()['workspace']['iterations'], old)
        self.assertEqual(self.desk.public['details'][0]['id'], region)

    def test_stored_cycle_and_future_references_rejected(self):
        idea = self.idea()
        first = self.record(self.node(idea))
        self.record(self.node(idea, parents=[first['selections'][idea]]))
        model = copy.deepcopy(self.model)
        model['nodes'][0]['parents'] = [model['nodes'][1]['id']]
        with self.assertRaisesRegex(ValueError, 'acyclic'):
            design.validate(model, {self.sha}, set())
        model = copy.deepcopy(self.model)
        model['checkpoints'][0]['selections'][idea] = model['nodes'][1]['id']
        with self.assertRaises(ValueError):
            design.validate(model, {self.sha}, set())
