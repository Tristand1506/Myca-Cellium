"""Strict private Review Desk records; never consumed by the Pages builder."""
import copy
import math
import re
import uuid

from review_metadata import require

FEATURES = {'cap', 'lichen', 'face', 'eyes', 'tissue', 'arms-hands', 'legs',
            'locomotion', 'baseline-skirt', 'membrane', 'pose', 'other'}
SEVERITIES = {'info', 'minor', 'major', 'critical'}
REVIEW_STATUSES = {'open', 'in-progress', 'resolved', 'dismissed'}
KINDS = {'rectangle', 'arrow', 'ellipse', 'pin', 'freehand'}


def empty():
    return {'schema_version': 1, 'annotations': [], 'comparisons': [], 'iterations': []}


def fields(value, names, label):
    require(isinstance(value, dict) and set(value) == set(names.split()), 'Invalid ' + label + ' fields')


def text(value, limit=20000, nonempty=False):
    require(isinstance(value, str) and len(value) <= limit
            and (not nonempty or bool(value.strip())), 'Invalid private text')


def member(value, choices, label):
    require(isinstance(value, str) and value in choices, 'Invalid ' + label)


def number(value, low=0, high=1):
    require(type(value) in (int, float) and math.isfinite(value) and low <= value <= high,
            'Coordinates must be finite and within bounds')


def identity(value):
    require(isinstance(value, str) and re.fullmatch(r'[a-z0-9-]{1,80}', value), 'Invalid private ID')


def target(value, targets):
    require(isinstance(value, str) and value in targets, 'Unknown image or saved region')


def validate(workspace, public, images):
    require(isinstance(workspace, dict) and {'schema_version','annotations'} <= set(workspace)
            and set(workspace) <= {'schema_version','annotations','comparisons','iterations'}, 'Invalid workspace fields')
    require(type(workspace['schema_version']) is int and workspace['schema_version'] == 1,
            'Unsupported private workspace schema')
    targets = set(images) | {d['id'] for d in public['details']}
    annotations = workspace['annotations']
    require(isinstance(annotations, list) and len(annotations) <= 10000, 'Invalid annotations')
    ids = set()
    for annotation in annotations:
        fields(annotation, 'id target kind points comment feature severity status', 'annotation')
        identity(annotation['id'])
        require(annotation['id'] not in ids, 'Duplicate annotation ID')
        ids.add(annotation['id']); target(annotation['target'], targets)
        member(annotation['kind'], KINDS, 'mark kind')
        member(annotation['feature'], FEATURES, 'feature')
        member(annotation['severity'], SEVERITIES, 'severity')
        member(annotation['status'], REVIEW_STATUSES, 'annotation status')
        text(annotation['comment'])
        points = annotation['points']
        require(isinstance(points, list) and 1 <= len(points) <= 2048, 'Invalid mark points')
        for point in points:
            require(isinstance(point, list) and len(point) == 2, 'Invalid mark point')
            for value in point:
                number(value)
        kind = annotation['kind']
        require(len(points) == (1 if kind == 'pin' else 2) or
                (kind == 'freehand' and len(points) >= 2), 'Wrong number of mark points')
        if kind in {'rectangle', 'ellipse'}:
            require(points[0][0] != points[1][0] and points[0][1] != points[1][1],
                    'Mark must have positive area')
        if kind == 'arrow':
            require(points[0] != points[1], 'Arrow must have length')
    comparisons = workspace.get('comparisons', [])
    require(isinstance(comparisons, list) and len(comparisons) <= 1000, 'Invalid comparisons')
    ids = set()
    for comparison in comparisons:
        fields(comparison, 'id name items transforms synchronized mode opacity split', 'comparison')
        identity(comparison['id'])
        require(comparison['id'] not in ids, 'Duplicate comparison ID'); ids.add(comparison['id'])
        text(comparison['name'], 160, nonempty=True)
        items = comparison['items']
        require(isinstance(items, list) and 2 <= len(items) <= 4, 'Compare two to four items')
        for item in items:
            target(item, targets)
        require(len(items) == len(set(items)), 'Duplicate comparison item')
        require(type(comparison['synchronized']) is bool, 'Invalid synchronization setting')
        member(comparison['mode'], {'side-by-side','overlay','slider'}, 'comparison mode')
        require(comparison['mode'] == 'side-by-side' or len(items) == 2, 'Layered comparison needs two items')
        number(comparison['opacity']); number(comparison['split'])
        transforms = comparison['transforms']
        require(isinstance(transforms, list) and len(transforms) == len(items), 'Invalid transforms')
        for transform in transforms:
            fields(transform, 'zoom pan alignment', 'transform')
            number(transform['zoom'], .1, 16)
            for pair in (transform['pan'], transform['alignment'].get('offset') if isinstance(transform['alignment'],dict) else None):
                require(isinstance(pair,list) and len(pair)==2, 'Invalid transform offset')
                for value in pair:
                    number(value,-8,8)
            fields(transform['alignment'], 'offset scale rotation', 'alignment')
            number(transform['alignment']['scale'], .1, 10)
            number(transform['alignment']['rotation'], -180, 180)
    iterations = workspace.get('iterations', [])
    require(isinstance(iterations,list) and len(iterations) <= 1000, 'Invalid iterations')
    nodes = {}
    for iteration in iterations:
        fields(iteration,'id asset_sha256 title relationship parents features corrections prompt outcome','iteration')
        identity(iteration['id'])
        require(iteration['id'] not in nodes,'Duplicate iteration ID')
        nodes[iteration['id']] = iteration
        target(iteration['asset_sha256'], set(images))
        text(iteration['title'],160,nonempty=True)
        member(iteration['relationship'], {'source','revision','alternative'}, 'iteration relationship')
        require(isinstance(iteration['parents'],list) and all(isinstance(p,str) for p in iteration['parents'])
                and len(iteration['parents']) == len(set(iteration['parents'])), 'Invalid parents')
        require((iteration['relationship']=='source' and not iteration['parents']) or
                (iteration['relationship']!='source' and bool(iteration['parents'])),
                'Sources have no parents; revisions and alternatives need a parent')
        features = iteration['features']
        require(isinstance(features,list) and all(isinstance(f,str) and f in FEATURES for f in features)
                and len(features)==len(set(features)), 'Invalid targeted features')
        text(iteration['corrections']); text(iteration['prompt'])
        member(iteration['outcome'], {'unreviewed','needs-refinement','reviewed','rejected'}, 'review outcome')
    indegree = {key:len(node['parents']) for key,node in nodes.items()}
    children = {key:[] for key in nodes}
    for key,node in nodes.items():
        for parent in node['parents']:
            require(parent in nodes and parent != key,'Missing or self-referencing iteration parent')
            children[parent].append(key)
    ready = [key for key,count in indegree.items() if count==0]
    seen = 0
    while ready:
        key = ready.pop(); seen += 1
        for child in children[key]:
            indegree[child] -= 1
            if indegree[child]==0:
                ready.append(child)
    require(seen==len(nodes),'Iteration relationships must be acyclic')
    return workspace


def validate_private(private, public, images):
    require(isinstance(private, dict) and set(private) <= {'version', 'notes', 'history', 'workspace'}
            and {'version', 'notes', 'history'} <= set(private), 'Invalid private state')
    require(type(private['version']) is int and private['version'] >= 0, 'Invalid private version')
    require(isinstance(private['notes'], dict), 'Invalid notes')
    targets = set(images) | {d['id'] for d in public['details']}
    for key, note in private['notes'].items():
        target(key, targets); text(note)
    history = private['history']
    require(isinstance(history, list) and len(history) <= 100, 'Invalid Undo history')
    validate(private.get('workspace', empty()), public, images)
    for entry in history:
        require(isinstance(entry, dict) and set(entry) <= {'public', 'notes', 'workspace'}
                and {'public', 'notes'} <= set(entry), 'Invalid Undo entry')
        from review_metadata import validate_metadata
        # Image-only surrogate is enough for validating the public organization.
        manifest = {'assets': list(images.values())}
        validate_metadata(entry['public'], manifest)
        validate(entry.get('workspace', empty()), entry['public'], images)
        require(isinstance(entry['notes'], dict), 'Invalid Undo notes')
        old_targets = set(images) | {d['id'] for d in entry['public']['details']}
        for key, note in entry['notes'].items():
            target(key, old_targets); text(note)


def save_record(records, payload, prefix):
    value = copy.deepcopy(payload.get('record'))
    require(isinstance(value, dict), 'Record required')
    requested = value.get('id')
    if requested is None:
        value['id'] = prefix + '-' + uuid.uuid4().hex
        records.append(value)
    else:
        identity(requested)
        index = next((i for i, record in enumerate(records) if record['id'] == requested), None)
        require(index is not None, 'Unknown record')
        records[index] = value


def delete_record(records, value):
    require(isinstance(value, str), 'Record ID required')
    match = next((record for record in records if record['id'] == value), None)
    require(match is not None, 'Unknown record')
    records.remove(match)


def mutate(workspace, payload):
    action = payload['action']
    if action == 'annotation_save':
        save_record(workspace['annotations'], payload, 'mark')
    elif action == 'annotation_delete':
        delete_record(workspace['annotations'], payload.get('id'))
    elif action == 'comparison_save':
        save_record(workspace.setdefault('comparisons', []), payload, 'compare')
    elif action == 'comparison_delete':
        delete_record(workspace.setdefault('comparisons', []), payload.get('id'))
    elif action == 'iteration_save':
        save_record(workspace.setdefault('iterations', []), payload, 'iteration')
    elif action == 'iteration_delete':
        value = payload.get('id')
        require(not any(value in node['parents'] for node in workspace.get('iterations', [])),
                'Edit child relationships before deleting their parent')
        delete_record(workspace.setdefault('iterations', []), value)
    else:
        raise ValueError('Unknown workspace action')


def remove_target(workspace, value):
    workspace['annotations'] = [a for a in workspace['annotations'] if a['target'] != value]

    workspace['comparisons'] = [c for c in workspace.get('comparisons', []) if value not in c['items']]
