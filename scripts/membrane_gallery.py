"""Comparable membrane galleries from public collection memberships."""
import json
import re

import review_metadata as meta
from feature_references import reference_notes
from site_gallery import esc, image_url

CONFIG_PATH = 'data/membrane-layout.json'


def identity(value):
    return isinstance(value, str) and re.fullmatch(r'[a-z0-9-]{1,64}', value)


def public_text(value, limit):
    from resource_library import OWNER_ID, OWNER_PATH, PRIVATE_URL
    return (isinstance(value, str) and 0 < len(value.strip()) <= limit
            and not any(ord(c) < 32 for c in value)
            and not re.search(r'[A-Za-z]:[\\/]|file://', value)
            and not any(p.search(value) for p in (OWNER_ID, OWNER_PATH, PRIVATE_URL)))


def load_layout(root):
    path = meta.safe_path(root, CONFIG_PATH)
    config = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {
        'schema_version': 1, 'source_collection': 'membranes', 'directions': []}
    meta.require(isinstance(config, dict) and set(config) == {'schema_version', 'source_collection', 'directions'}
                 and type(config['schema_version']) is int and config['schema_version'] == 1
                 and identity(config['source_collection']), 'Invalid membrane layout schema')
    meta.require(isinstance(config['directions'], list) and len(config['directions']) <= 100,
                 'Invalid membrane directions')
    ids, collections = set(), set()
    for direction in config['directions']:
        meta.require(isinstance(direction, dict) and set(direction) ==
                     {'id', 'collection_id', 'title', 'summary', 'basis'}, 'Invalid membrane direction fields')
        meta.require(identity(direction['id']) and direction['id'] != 'unsorted'
                     and identity(direction['collection_id'])
                     and direction['collection_id'] != config['source_collection'],
                     'Invalid membrane direction ID')
        meta.require(direction['id'] not in ids and direction['collection_id'] not in collections,
                     'Duplicate membrane direction')
        ids.add(direction['id']); collections.add(direction['collection_id'])
        meta.require(public_text(direction['title'], 160) and public_text(direction['summary'], 400)
                     and isinstance(direction['basis'], str)
                     and direction['basis'] in {'documented candidate', 'organizational experiment', 'comparison sheets'},
                     'Invalid membrane direction labels')
    return config


def direction_items(metadata, config):
    """Whole sheets and virtual regions stay distinct; archived parents stay hidden."""
    collections = {c['id']: c for c in metadata['collections']}
    details = {d['id']: d for d in metadata['details']}
    archived = set(metadata['archived'])

    def members(collection):
        result = [{'id': sha, 'asset_sha256': sha, 'detail': None} for sha in collection['assets']
                  if sha not in archived]
        regions = [{'id': identity, 'asset_sha256': details[identity]['asset_sha256'], 'detail': details[identity]}
                   for identity in collection['details'] if details[identity]['asset_sha256'] not in archived]
        return regions + result

    empty = {'assets': [], 'details': []}
    source = collections.get(config['source_collection'], empty)
    groups, assigned = [], set()
    for direction in config['directions']:
        collection = collections.get(direction['collection_id'], empty)
        items = members(collection)
        assigned.update(item['id'] for item in items)
        hidden = sum(sha in archived for sha in collection['assets']) + sum(
            details[d]['asset_sha256'] in archived for d in collection['details'])
        groups.append({**direction, 'items': items, 'archived_count': hidden})
    remaining = [item for item in members(source) if item['id'] not in assigned]
    groups.append({'id': 'unsorted', 'collection_id': config['source_collection'],
                   'title': 'Unsorted studies', 'summary': 'Assigned membrane studies without a direction membership.',
                   'basis': 'organization only', 'items': remaining, 'archived_count': 0})
    return groups


def preview(asset, detail, title):
    image = f'<img src="{image_url(asset)}" alt="{esc(title)}" loading="lazy" decoding="async"'
    if not detail:
        return '<div class="membrane-preview">' + image + '></div>'
    l, t, r, b = detail['rect']
    style = f'width:{100/(r-l):.6f}%;height:{100/(b-t):.6f}%;left:{-100*l/(r-l):.6f}%;top:{-100*t/(b-t):.6f}%'
    return (f'<div class="membrane-preview"><div class="membrane-region" data-region-width="{r-l}" data-region-height="{b-t}">'
            + image + f' style="{style}"></div></div>')


def comparison_card(item, asset, references, direction, parents=None):
    detail = item['detail']
    title = detail['title'] if detail else asset['stored_filename']
    parent = ' / '.join(r['reference_id'] for r in references) or 'Unregistered artwork'
    body = f'<article class="membrane-item" data-compare-id="{item["id"]}"><div class="compare-picker" hidden><label><input type="checkbox" data-compare-select aria-label="Compare {esc(title)}"> Add to comparison</label></div>'
    body += preview(asset, detail, title)
    body += f'<div class="card-body"><p class="eyebrow">{esc(direction["title"])}</p><h3>{esc(title)}</h3><p>{esc(parent)} · Comparison only; no new approval</p>'
    body += f'<p class="muted">{esc("; ".join(asset["classification"]))}</p>'
    body += f'<a href="{image_url(asset)}">Open unchanged original</a>'
    if detail:
        body += f'<p class="crop-meta">Linked region: {esc(detail["rect"])}. No new bitmap or R/C ID.</p>'
    body += '<details class="comparison-limits"><summary>Recorded scope and limitations</summary>'
    body += ''.join(reference_notes(r) for r in references) or '<p>No recorded feature approval. Current written rules govern.</p>'
    if parents:
        body += '<h4>Crop-parent limitations</h4>' + ''.join(reference_notes(r) for r in parents)
    body += '</details></div></article>'
    return body


def membrane_page(manifest, metadata, config):
    meta.validate_metadata(metadata, manifest)
    assets = {a['sha256']: a for a in manifest['assets']}
    references = {}
    by_id = {r['reference_id']: r for r in manifest['references']}
    for reference in manifest['references']:
        for sha in reference['asset_sha256']:
            references.setdefault(sha, []).append(reference)
    groups = direction_items(metadata, config)
    body = '<p class="kicker">Separate ideas · comparable views</p><h1>Membrane directions</h1><p class="lede">Explore each growth architecture separately, then compare two to four studies side by side.</p>'
    body += '<p class="notice experiment-notice">All directions are working experimental groups. Membership and display regions grant no feature approval. The pink skirt and dark waistband remain the baseline; living-membrane studies follow the no-belt, grown-from-body construction.</p>'
    body += '<p>Frames use the same display height and preserve image proportions. Source poses, scale and lighting still differ. <a href="experiments.html">All experimental originals</a> · <a href="../docs/Myca%20Character%20Design%20Brief.html">Written construction rules</a></p>'
    body += '<div class="membrane-tools" hidden><label>Show direction <select id="membrane-direction"><option value="all">All directions</option>'
    body += ''.join(f'<option value="{g["id"]}">{esc(g["title"])}</option>' for g in groups)
    body += '</select></label><p id="membrane-selection-status" role="status" aria-live="polite">Choose two to four studies.</p><button type="button" id="membrane-compare-button" disabled>Compare selected</button><button type="button" id="membrane-clear">Clear selection</button></div>'
    body += '<section id="membrane-comparison" class="page" hidden aria-labelledby="membrane-comparison-title"><h2 id="membrane-comparison-title">Side-by-side comparison</h2><p>Compare attachment, layering, edge shape and openness. Keep the recorded limitations in view.</p><div class="membrane-comparison-scroll" tabindex="0" aria-label="Scrollable comparison"><div id="membrane-comparison-grid"></div></div></section>'
    body += '<nav class="gallery-tabs" aria-label="Membrane directions">' + ''.join(
        f'<a href="#direction-{g["id"]}" data-direction-link="{g["id"]}">{esc(g["title"])} ({len(g["items"])})</a>' for g in groups) + '</nav>'
    for group in groups:
        body += f'<section id="direction-{group["id"]}" class="membrane-direction" data-direction="{group["id"]}"><header><p class="kicker">{esc(group["basis"])}</p><h2>{esc(group["title"])}</h2><p>{esc(group["summary"])}</p>'
        if group['collection_id'] in {c['id'] for c in metadata['collections']}:
            body += f'<p><a href="collections.html#collection-{group["collection_id"]}">Saved collection assignments</a></p>'
        if group['archived_count']:
            body += f'<p>{group["archived_count"]} archived membership(s) retained outside active comparison.</p>'
        body += '</header><div class="membrane-grid">'
        for item in group['items']:
            refs = references.get(item['asset_sha256'], [])
            parent_ids = dict.fromkeys(r['crop']['parent_reference_id'] for r in refs if r.get('crop') and r['crop']['parent_reference_id'] != r['reference_id'])
            parents = [by_id[rid] for rid in parent_ids if rid in by_id]
            body += comparison_card(item, assets[item['asset_sha256']], refs, group, parents)
        if not group['items']:
            body += '<p class="notice">No active studies assigned to this direction yet.</p>'
        body += '</div></section>'
    body += '<script src="../membrane-compare.js" defer></script>'
    return body
