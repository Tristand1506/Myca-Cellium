"""Private idea history. Checkpoints select immutable iterations; they never approve canon."""
import copy
import uuid
from datetime import datetime, timezone
from review_metadata import require

ACTIONS = {'idea_create', 'idea_update', 'branch_create', 'branch_update',
           'design_checkpoint', 'design_metadata'}
OUTCOMES = {'unreviewed', 'needs-refinement', 'reviewed', 'rejected'}
LIFECYCLES = {'current', 'legacy', 'obsolete'}


def empty():
    return {'ideas': [], 'branches': [], 'nodes': [], 'checkpoints': [],
            'head': None, 'metadata': {}, 'audit': []}


def keyed(records):
    return {record['id']: record for record in records}


def unique(values, allowed, label):
    require(isinstance(values, list) and all(isinstance(v, str) for v in values)
            and len(values) == len(set(values)) and set(values) <= allowed, 'Invalid ' + label)


def dag(records, label):
    records = keyed(records)
    remaining = {key: set(record['parents']) for key, record in records.items()}
    require(all(parents <= records.keys() and key not in parents for key, parents in remaining.items()),
            'Invalid ' + label + ' parent')
    children = {key: [] for key in remaining}
    for key, parents in remaining.items():
        for parent in parents:
            children[parent].append(key)
    ready = [key for key, parents in remaining.items() if not parents]
    visited = 0
    while ready:
        key = ready.pop()
        visited += 1
        for child in children[key]:
            remaining[child].remove(key)
            if not remaining[child]:
                ready.append(child)
    require(visited == len(records), label + ' relationships must be acyclic')


def validate(value, targets, legacy):
    from review_workspace import fields, identity, text, member, FEATURES, FAMILIES
    fields(value, 'ideas branches nodes checkpoints head metadata audit', 'design history')
    for key, limit in [('ideas', 200), ('branches', 1000), ('nodes', 5000), ('checkpoints', 5000)]:
        records = value[key]
        require(isinstance(records, list) and len(records) <= limit, 'Invalid ' + key)
        ids = set()
        for record in records:
            require(isinstance(record, dict), 'Invalid ' + key + ' record')
            identity(record.get('id'))
            require(record['id'] not in ids, 'Duplicate ' + key + ' ID')
            ids.add(record['id'])
    ideas, branches, nodes, checkpoints = [keyed(value[key]) for key in
                                         ('ideas', 'branches', 'nodes', 'checkpoints')]
    for idea in ideas.values():
        fields(idea, 'id name feature family experimental', 'idea')
        text(idea['name'], 160, nonempty=True)
        member(idea['feature'], FEATURES, 'idea feature')
        member(idea['family'], FAMILIES, 'idea family')
        require(type(idea['experimental']) is bool, 'Invalid idea experimental flag')
    for branch in branches.values():
        fields(branch, 'id idea_id name experimental parents base head', 'branch')
        require(isinstance(branch['idea_id'], str) and branch['idea_id'] in ideas, 'Unknown branch idea')
        text(branch['name'], 160, nonempty=True)
        require(type(branch['experimental']) is bool, 'Invalid branch experimental flag')
        unique(branch['parents'], branches.keys(), 'branch parents')
        for key in ('base', 'head'):
            require(branch[key] is None or isinstance(branch[key], str) and branch[key] in checkpoints,
                    'Unknown branch checkpoint')
        if branch['head']:
            require(checkpoints[branch['head']]['route'] == branch['id'], 'Wrong branch head route')
    dag(value['branches'], 'Branch')
    for node in nodes.values():
        fields(node, 'id idea_id branch_id title targets prompt corrections parents contributions legacy_id', 'design iteration')
        require(isinstance(node['idea_id'], str) and node['idea_id'] in ideas, 'Unknown iteration idea')
        require(node['branch_id'] is None or isinstance(node['branch_id'], str) and node['branch_id'] in branches,
                'Unknown iteration branch')
        if node['branch_id']:
            require(branches[node['branch_id']]['idea_id'] == node['idea_id'], 'Wrong iteration branch idea')
        text(node['title'], 160, nonempty=True)
        text(node['prompt']); text(node['corrections'])
        unique(node['targets'], targets, 'iteration artwork')
        unique(node['parents'], nodes.keys(), 'iteration parents')
        require(all(nodes[parent]['idea_id'] == node['idea_id'] for parent in node['parents']),
                'Iteration parents must describe the same idea')
        require(node['legacy_id'] is None or isinstance(node['legacy_id'], str) and node['legacy_id'] in legacy,
                'Unknown unassigned iteration')
        require(isinstance(node['contributions'], list) and len(node['contributions']) <= 100,
                'Invalid contributions')
        contributor_ids = []
        for contribution in node['contributions']:
            fields(contribution, 'node_id detail', 'contribution')
            require(isinstance(contribution['node_id'], str) and contribution['node_id'] in node['parents'],
                    'Contributions must reference iteration parents')
            text(contribution['detail'], nonempty=True)
            contributor_ids.append(contribution['node_id'])
        require(len(contributor_ids) == len(set(contributor_ids)), 'Duplicate contribution')
        require(len(node['parents']) < 2 or set(contributor_ids) == set(node['parents']),
                'Describe the contribution from each combined parent')
    dag(value['nodes'], 'Iteration')
    recorded = set()
    for checkpoint in checkpoints.values():
        fields(checkpoint, 'id name route parents selections updates created_at', 'checkpoint')
        text(checkpoint['name'], 160, nonempty=True); text(checkpoint['created_at'], 80, nonempty=True)
        require(checkpoint['route'] == 'mainline' or isinstance(checkpoint['route'], str)
                and checkpoint['route'] in branches, 'Unknown checkpoint route')
        unique(checkpoint['parents'], checkpoints.keys(), 'checkpoint parents')
        selections = checkpoint['selections']
        require(isinstance(selections, dict) and set(selections) <= ideas.keys(), 'Invalid checkpoint ideas')
        require(all(isinstance(node_id, str) and node_id in nodes and nodes[node_id]['idea_id'] == idea_id
                    for idea_id, node_id in selections.items()), 'Invalid checkpoint iteration')
        unique(checkpoint['updates'], nodes.keys(), 'checkpoint updates')
        require(set(checkpoint['updates']) <= set(selections.values()), 'Checkpoint updates must be selected')
        require(not (recorded & set(checkpoint['updates'])), 'Iteration already recorded in another checkpoint')
        recorded.update(checkpoint['updates'])
    dag(value['checkpoints'], 'Checkpoint')
    require(recorded == nodes.keys(), 'Every iteration must be recorded at a checkpoint')
    # Content and ancestry must already exist when a checkpoint is recorded.
    positions = {c['id']: index for index, c in enumerate(value['checkpoints'])}
    birth = {n: positions[c['id']] for c in value['checkpoints'] for n in c['updates']}
    for checkpoint in checkpoints.values():
        require(all(positions[parent] < positions[checkpoint['id']] for parent in checkpoint['parents']),
                'Checkpoint parent must be earlier')
        require(all(birth[n] <= positions[checkpoint['id']] for n in checkpoint['selections'].values()),
                'Checkpoint cannot select a future iteration')
    require(all(birth[parent] < birth[node['id']] for node in nodes.values() for parent in node['parents']),
            'Iteration parent must be earlier')
    require(value['head'] is None or isinstance(value['head'], str) and value['head'] in checkpoints
            and checkpoints[value['head']]['route'] == 'mainline', 'Invalid mainline head')
    metadata = value['metadata']
    require(isinstance(metadata, dict) and set(metadata) == nodes.keys(), 'Invalid iteration metadata')
    for record in metadata.values():
        fields(record, 'notes outcome lifecycle candidate nomination_reason', 'iteration metadata')
        text(record['notes']); text(record['nomination_reason'])
        member(record['outcome'], OUTCOMES, 'iteration outcome')
        member(record['lifecycle'], LIFECYCLES, 'iteration lifecycle')
        require(type(record['candidate']) is bool, 'Invalid iteration nomination')
    require(isinstance(value['audit'], list) and len(value['audit']) <= 10000, 'Invalid metadata audit')
    for entry in value['audit']:
        fields(entry, 'node_id before after created_at', 'metadata audit')
        require(isinstance(entry['node_id'], str) and entry['node_id'] in nodes, 'Unknown audited iteration')
        text(entry['created_at'], 80, nonempty=True)
        for record in (entry['before'], entry['after']):
            fields(record, 'notes outcome lifecycle candidate nomination_reason', 'audited metadata')
            text(record['notes']); text(record['nomination_reason'])
            member(record['outcome'], OUTCOMES, 'audit outcome')
            member(record['lifecycle'], LIFECYCLES, 'audit lifecycle')
            require(type(record['candidate']) is bool, 'Invalid audited nomination')
    return value


def context(value, branch_id=None):
    checkpoints = keyed(value['checkpoints'])
    selections = copy.deepcopy(checkpoints[value['head']]['selections']) if value['head'] else {}
    if branch_id:
        branch = keyed(value['branches'])[branch_id]
        origin = branch['head'] or branch['base']
        # Other ideas follow the latest working context; this idea keeps its branch choice.
        if origin:
            own = checkpoints[origin]['selections'].get(branch['idea_id'])
            if own:
                selections[branch['idea_id']] = own
    return selections


def new_id(prefix):
    return prefix + '-' + uuid.uuid4().hex


def now():
    return datetime.now(timezone.utc).isoformat()


def mutate(value, payload):
    from review_workspace import fields
    action = payload['action']
    if action in {'idea_create', 'branch_create'}:
        record = copy.deepcopy(payload.get('record'))
        require(isinstance(record, dict), 'Record required')
        if action == 'idea_create':
            fields(record, 'name feature family experimental', 'new idea')
            value['ideas'].append({'id': new_id('idea'), **record})
        else:
            fields(record, 'idea_id name experimental parents base', 'new branch')
            value['branches'].append({'id': new_id('branch'), 'head': None, **record})
    elif action in {'idea_update', 'branch_update'}:
        key = 'ideas' if action == 'idea_update' else 'branches'
        record = keyed(value[key]).get(payload.get('id'))
        require(record is not None, 'Unknown ' + key)
        changes = copy.deepcopy(payload.get('changes'))
        allowed = {'name', 'feature', 'family', 'experimental'} if key == 'ideas' else {'name', 'experimental'}
        require(isinstance(changes, dict) and set(changes) <= allowed, 'Invalid label changes')
        record.update(changes)
    elif action == 'design_metadata':
        node_id = payload.get('id')
        require(isinstance(node_id, str) and node_id in value['metadata'], 'Unknown iteration')
        record = copy.deepcopy(payload.get('record'))
        fields(record, 'notes outcome lifecycle candidate nomination_reason', 'iteration metadata')
        before = value['metadata'][node_id]
        if record != before:
            require(len(value['audit']) < 10000, 'Metadata audit is full')
            value['audit'].append({'node_id': node_id, 'before': copy.deepcopy(before),
                                   'after': copy.deepcopy(record), 'created_at': now()})
            value['metadata'][node_id] = record
    elif action == 'design_checkpoint':
        route = payload.get('route', 'mainline')
        branches, checkpoints, ideas, nodes = [keyed(value[key]) for key in
                                              ('branches', 'checkpoints', 'ideas', 'nodes')]
        require(isinstance(route, str) and (route == 'mainline' or route in branches), 'Unknown checkpoint route')
        base = payload.get('base')
        require(base is None or isinstance(base, str) and base in checkpoints, 'Unknown starting checkpoint')
        selections = copy.deepcopy(checkpoints[base]['selections']) if base else context(value, None if route == 'mainline' else route)
        parents = [base] if base else []
        current = value['head'] if route == 'mainline' else branches[route]['head'] or branches[route]['base']
        for parent in (current, value['head'], payload.get('merge')):
            require(parent is None or isinstance(parent, str) and parent in checkpoints, 'Unknown merge checkpoint')
            if parent and parent not in parents:
                parents.append(parent)
        updates = payload.get('nodes', [])
        require(isinstance(updates, list) and len(updates) <= 200, 'Invalid new iterations')
        new_nodes = []
        for raw in updates:
            record = copy.deepcopy(raw)
            fields(record, 'idea_id branch_id title targets prompt corrections parents contributions legacy_id', 'new iteration')
            node = {'id': new_id('design'), **record}
            value['nodes'].append(node); new_nodes.append(node)
            value['metadata'][node['id']] = {'notes': '', 'outcome': 'unreviewed', 'lifecycle': 'current',
                                            'candidate': False, 'nomination_reason': ''}
        selected = payload.get('selections', {})
        require(isinstance(selected, dict) and set(selected) <= ideas.keys(), 'Invalid selected ideas')
        for idea_id, node_id in selected.items():
            require(isinstance(node_id, str), 'Invalid selected iteration')
            if node_id.startswith('$'):
                try:
                    index = int(node_id[1:])
                    require(node_id == '$' + str(index) and 0 <= index < len(new_nodes), 'Invalid staged iteration')
                    node_id = new_nodes[index]['id']
                except (ValueError, IndexError):
                    raise ValueError('Invalid staged iteration')
            selections[idea_id] = node_id
        require(set(n['id'] for n in new_nodes) <= set(selections.values()),
                'Select every new iteration in its checkpoint')
        require(len({n['idea_id'] for n in new_nodes}) == len(new_nodes), 'Only one new iteration per idea per checkpoint')
        if route != 'mainline':
            own = branches[route]['idea_id']
            require(all(n['idea_id'] == own and n['branch_id'] == route for n in new_nodes)
                    and set(selected) <= {own}, 'A contained branch changes only its own idea')
        checkpoint = {'id': new_id('checkpoint'), 'name': payload.get('name'), 'route': route,
                      'parents': parents, 'selections': selections, 'updates': [n['id'] for n in new_nodes],
                      'created_at': now()}
        require(bool(new_nodes or selected or base), 'Checkpoint needs a change or a restored context')
        value['checkpoints'].append(checkpoint)
        if route == 'mainline':
            value['head'] = checkpoint['id']
        else:
            branches[route]['head'] = checkpoint['id']
    else:
        raise ValueError('Unknown design action')
