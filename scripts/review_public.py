"""Publish curated collections and virtual regions, never local review notes."""
from site_gallery import card, controls, esc, image_url, is_experiment


def detail_card(detail, asset, reference=None):
    l, t, r, b = detail['rect']
    style = f'width:{100 / (r-l):.6f}%;height:{100 / (b-t):.6f}%;left:{-100*l/(r-l):.6f}%;top:{-100*t/(b-t):.6f}%'
    registry = reference['design_registry'] if reference else {}
    status = 'Experimental parent — not baseline canon' if is_experiment(asset) else 'Virtual detail view — no new approval'
    scope = registry.get('crop_scope') or registry.get('approved_scope') or 'No recorded feature approval. Use current written rules.'
    caveat = registry.get('known_defects') or 'All parent limitations still apply. A region does not correct artwork.'
    parent = reference['reference_id'] if reference else 'Unmapped asset ' + asset['sha256'][:16]
    title = detail['title']
    return (f'<article id="{detail["id"]}" class="asset-card" data-card data-kind="detail" data-search="{esc((title + " " + parent + " " + status + " " + scope + " " + caveat).lower())}">'
            f'<div class="saved-region" data-region-width="{r-l}" data-region-height="{b-t}"><img src="{image_url(asset)}" alt="{esc(title)}" loading="lazy" decoding="async" style="{style}"></div>'
            f'<div class="card-body"><p class="eyebrow">Saved view · parent {esc(parent)}</p><h2>{esc(title)}</h2>'
            f'<p class="status">{esc(status)}</p><div class="scope"><h3>Inherited use scope</h3><p>{esc(scope)}</p></div>'
            f'<div class="caveat"><h3>Parent caveats</h3><p>{esc(caveat)}</p></div>'
            f'<p>Normalized bounds: {esc(detail["rect"])}. No crop file or new R/C identifier.</p>'
            f'<a href="{image_url(asset)}">Open unchanged parent image ↗</a></div></article>')


def organization_pages(manifest, metadata):
    assets = {a['sha256']: a for a in manifest['assets']}
    refs = {sha: ref for ref in manifest['references'] for sha in ref['asset_sha256']}
    details = {d['id']: d for d in metadata['details']}
    body = '<p class="kicker">Creator-curated organization</p><h1>Feature collections</h1><p class="notice">Grouping and saved regions do not grant canon approval. Experimental parents stay experimental. Private review notes are not published.</p>'
    body += '<p><a href="features.html">Review feature assignments and recorded scopes</a></p>'
    if not metadata['collections']:
        body += '<p>No collections have been created yet.</p>'
    for collection in metadata['collections']:
        body += f'<section id="collection-{collection["id"]}"><h2>{esc(collection["name"])}</h2><div class="gallery-grid">'
        active_assets = [assets[sha] for sha in collection['assets'] if sha not in metadata['archived']]
        active_details = [details[identity] for identity in collection['details'] if details[identity]['asset_sha256'] not in metadata['archived']]
        for asset in active_assets:
            rendered = card(asset, refs.get(asset['sha256']))
            # Same image may be in several collections without duplicate DOM IDs.
            identity = refs[asset['sha256']]['reference_id'] if asset['sha256'] in refs else 'asset-' + asset['sha256'][:16]
            rendered = rendered.replace(f'id="{identity}"', f'id="{collection["id"]}-{identity}"', 1)
            body += rendered
        for detail in active_details:
            body += detail_card(detail, assets[detail['asset_sha256']], refs.get(detail['asset_sha256'])).replace(
                f'id="{detail["id"]}"', f'id="{collection["id"]}-{detail["id"]}"', 1)
        hidden = len(collection['assets']) + len(collection['details']) - len(active_assets) - len(active_details)
        if hidden:
            body += f'<p class="notice">{hidden} archived membership(s) retained. <a href="features.html#feature-{collection["id"]}">Review retained assignments</a>.</p>'
        if not active_assets and not active_details:
            body += '<p class="notice">No active items in this collection.</p>'
        body += '</div></section>'
    body += '<section><h2>All active saved detail views</h2><div class="gallery-grid">'
    for detail in metadata['details']:
        if detail['asset_sha256'] not in metadata['archived']:
            body += detail_card(detail, assets[detail['asset_sha256']], refs.get(detail['asset_sha256']))
    body += '</div></section><script src="../detail-views.js" defer></script>'
    archive = '<p class="kicker">Development history</p><h1>Archived artwork</h1><p class="notice">Archived means removed from active browsing, not deleted or made private. Reference identities, recorded scopes and original bytes remain intact.</p>'
    archive += controls([], len(metadata['archived'])) + '<div class="gallery-grid">'
    for sha in metadata['archived']:
        archive += card(assets[sha], refs.get(sha))
    archive += '</div>'
    return {'gallery/collections.html': body, 'gallery/archive.html': archive}
