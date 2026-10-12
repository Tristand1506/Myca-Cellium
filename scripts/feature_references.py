"""Derive organizational reference assignments without changing approval records."""
import copy
import json
import re

import review_metadata as meta
from site_gallery import esc, image_url

CONFIG_PATH = 'data/collection-features.json'
FEATURE_LABELS = {
    'cap': 'Mushroom cap',
    'lichen': 'Compact lichen bob',
    'face-eyes': 'Face and eyes',
    'tissue': 'Tissue and internal hyphae',
    'legs-contact': 'Legs and ground contact',
    'membrane-experiments': 'Living-membrane experiments',
}


def load_features(root):
    path = meta.safe_path(root, CONFIG_PATH)
    config = json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {
        'schema_version': 1, 'collection_features': {}}
    meta.require(isinstance(config, dict) and set(config) == {'schema_version', 'collection_features'}
                 and type(config['schema_version']) is int and config['schema_version'] == 1,
                 'Invalid collection-feature schema')
    mapping = config['collection_features']
    meta.require(isinstance(mapping, dict) and all(
        isinstance(identity, str) and re.fullmatch(r'[a-z0-9-]{1,64}', identity)
        and isinstance(feature, str) and feature in FEATURE_LABELS
        for identity, feature in mapping.items()), 'Invalid collection-feature mapping')
    # Deleted collections may retain their mapping for later restoration.
    return mapping


def assignments(manifest, metadata, mapping):
    """Membership assigns a review topic, never permission to copy that feature."""
    meta.validate_metadata(metadata, manifest)
    assets = {a['sha256']: a for a in manifest['assets']}
    refs = {}
    by_id = {r['reference_id']: r for r in manifest['references']}
    for reference in manifest['references']:
        for sha in reference['asset_sha256']:
            refs.setdefault(sha, []).append(reference)
    details = {d['id']: d for d in metadata['details']}
    collections = []
    assigned_assets = set()
    for collection in metadata['collections']:
        items = []
        members = [(sha, None) for sha in collection['assets']]
        members += [(details[identity]['asset_sha256'], details[identity])
                    for identity in collection['details']]
        assigned_assets.update(collection['assets'])
        for sha, detail in members:
            references = refs.get(sha, [])
            parent_ids = dict.fromkeys(r['crop']['parent_reference_id']
                                      for r in references if r.get('crop'))
            items.append({
                'asset_sha256': sha,
                'detail': copy.deepcopy(detail),
                'archived': sha in metadata['archived'],
                'classification': copy.deepcopy(assets[sha]['classification']),
                'references': copy.deepcopy(references),
                'parent_references': [copy.deepcopy(by_id[rid]) for rid in parent_ids if rid in by_id],
            })
        collections.append({
            'collection_id': collection['id'],
            'name': collection['name'],
            'feature_id': mapping.get(collection['id']),
            'items': items,
        })
    return {
        'schema_version': 1,
        'organization_revision': metadata['revision'],
        'membership_source': meta.PUBLIC_PATH,
        'feature_mapping_source': CONFIG_PATH,
        'interpretation': 'organizational membership only; no new feature approval',
        'collections': collections,
        # A saved region assigns only that region, not its whole parent image.
        'unassigned_asset_sha256': [a['sha256'] for a in manifest['assets']
                                    if meta.is_image(a) and a['sha256'] not in assigned_assets],
        'missing_reference_ids': [r['reference_id'] for r in manifest['references']
                                  if not r['asset_sha256']],
    }


def reference_notes(reference):
    registry = reference['design_registry']
    result = f'<p><strong>{esc(reference["reference_id"])}</strong> · {esc(registry.get("status") or "No separate status recorded; inherited limitations apply.")}</p>'
    scope = registry.get('crop_scope') if reference.get('crop') else registry.get('approved_scope')
    result += f'<p><strong>Recorded scope:</strong> {esc(scope or "No feature approval recorded.")}</p>'
    if registry.get('known_defects'):
        result += f'<p><strong>Do not inherit:</strong> {esc(registry["known_defects"])}</p>'
    if reference.get('crop'):
        crop = reference['crop']
        result += f'<p>Exact crop of {esc(crop["parent_reference_id"])} · bounds {esc(crop["bounds_px"])} · {esc(crop["size_px"])} px.</p>'
    return result


def feature_page(manifest, derived):
    assets = {a['sha256']: a for a in manifest['assets']}
    body = '<p class="kicker">Collection-based navigation</p><h1>References by feature</h1><p class="lede">Review the images you assigned to each topic beside their existing reference limits.</p>'
    body += '<p class="notice">Collection membership is organization, not creator approval of that feature. Recorded scopes, statuses and parent caveats still govern. A face collection may contain a lichen-only reference; an experimental image stays experimental.</p>'
    body += '<p><a href="collections.html">Browse collection images</a> · <a href="../feature-references.json">Download reference assignments</a></p>'
    if not derived['collections']:
        body += '<p>No saved collection assignments are available.</p>'
    else:
        body += '<ul class="doc-links">' + ''.join(
            f'<li><a href="#feature-{c["collection_id"]}">{esc(c["name"])}</a></li>'
            for c in derived['collections']) + '</ul>'
    for collection in derived['collections']:
        feature = collection['feature_id']
        topic = FEATURE_LABELS[feature] if feature else 'Organization only; no feature mapping'
        active = sum(not item['archived'] for item in collection['items'])
        body += f'<section class="page" id="feature-{collection["collection_id"]}"><h2>{esc(collection["name"])}</h2><p>Review topic: {esc(topic)}. {active} active / {len(collection["items"])} saved memberships.</p>'
        body += f'<p><a href="collections.html#collection-{collection["collection_id"]}">Open this collection</a></p>'
        if not collection['items']:
            body += '<p>No items assigned.</p>'
        else:
            body += '<div class="assignment-table"><table><thead><tr><th>Assigned item</th><th>Existing scope and status</th><th>Parent limitations</th></tr></thead><tbody>'
            for item in collection['items']:
                asset = assets[item['asset_sha256']]
                title = item['detail']['title'] if item['detail'] else asset['stored_filename']
                state = 'Archived; excluded from active collections' if item['archived'] else 'Active'
                body += f'<tr><td><strong>{esc(title)}</strong><p>{state}</p><p>{esc("; ".join(item["classification"]))}</p><a href="{image_url(asset)}">Open unchanged original</a>'
                if item['detail']:
                    body += f'<p>Saved region {esc(item["detail"]["id"])} · normalized bounds {esc(item["detail"]["rect"])}. No new crop or R/C ID.</p>'
                body += '</td><td>'
                body += ''.join(reference_notes(r) for r in item['references']) or '<p>Unregistered artwork. No R/C ID or feature approval assigned.</p>'
                body += '</td><td>'
                body += ''.join(reference_notes(r) for r in item['parent_references']) or '<p>Use the recorded limitations and current written rules.</p>'
                body += '</td></tr>'
            body += '</tbody></table></div>'
        body += '</section>'
    body += f'<section class="page"><h2>Assignment coverage</h2><p>{len(derived["unassigned_asset_sha256"])} original images have no direct collection membership. Saved regions assign only their selected area.</p>'
    body += f'<p>Missing or unmapped reference IDs: {esc(", ".join(derived["missing_reference_ids"]) or "none")}. Their identifiers remain reserved.</p></section>'
    return body
