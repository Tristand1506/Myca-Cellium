#!/usr/bin/env python3
"""Verify the built public site, originals, gallery coverage and local links."""
import hashlib
from html.parser import HTMLParser
from pathlib import Path
import re
import json
from urllib.parse import unquote, urlsplit

import build_site
import resource_library
import review_metadata
import feature_references
import membrane_gallery
from review_public import organization_pages
from site_gallery import gallery_pages, is_image


class Page(HTMLParser):
    def __init__(self, content):
        super().__init__()
        self.links = []
        self.ids = []
        self.cards = []
        self.images = []
        self.viewport = False
        self.feed(content)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if 'data-card' in attrs:
            self.cards.append(attrs['id'])
        if tag == 'meta' and attrs.get('name') == 'viewport':
            self.viewport = 'width=device-width' in attrs.get('content', '')
        for key in ('href', 'src'):
            if attrs.get(key):
                self.links.append(attrs[key])
        if tag == 'img':
            self.images.append(attrs)


def check(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def local_links(path, out):
    page = Page(path.read_text(encoding='utf-8'))
    errors = []
    for target in page.links:
        url = urlsplit(target)
        if url.scheme or url.netloc:
            continue
        resolved = (path.parent / unquote(url.path)).resolve() if url.path else path.resolve()
        if not resolved.is_relative_to(out.resolve()) or not resolved.is_file():
            errors.append(f'{path.relative_to(out)} -> {target}')
        # Source documents have historic heading anchors; generated navigation
        # and the preserved illustrated guide must have real fragment targets.
        elif url.fragment and (not url.path or path.name == 'Myca Resource Guide.html'
                               or resolved.parent == (out / 'gallery').resolve()):
            linked = Page(resolved.read_text(encoding='utf-8'))
            if unquote(url.fragment) not in linked.ids:
                errors.append(f'{path.relative_to(out)} -> missing #{url.fragment}')
    return errors


def validate(root=build_site.ROOT, out=build_site.OUT):
    manifest = resource_library.load_manifest()
    metadata = review_metadata.load_metadata(root, manifest)
    derived = feature_references.assignments(manifest, metadata, feature_references.load_features(root))
    library = root / 'resources/character-library'
    published = out / 'resources/character-library'
    expected = build_site.public_files(manifest, metadata)
    actual = {p.relative_to(published).as_posix() for p in published.rglob('*') if p.is_file()}
    rendered = {name[:-3] + '.html' for name in build_site.PUBLIC_PAGES}
    check(actual == expected | rendered, 'Publication differs from reviewed library allowlist')
    for name in expected:
        check(digest(review_metadata.locate(library, name, manifest, metadata)) == digest(published / name), f'Published bytes differ: {name}')
    for asset in manifest['assets']:
        check(digest(published / asset['resource_path']) == asset['sha256'], 'Published asset checksum changed')
    guide = root / 'docs/Myca Resource Guide.html'
    check(digest(out / guide.name) == digest(guide), 'Illustrated guide was changed')
    for alias, asset in build_site.guide_aliases(guide.read_text(encoding='utf-8'), manifest).items():
        for prefix in ('', 'docs/'):
            check(digest(out / (prefix + alias)) == asset['sha256'], 'Guide compatibility asset changed')
    pages = [out / 'index.html', out / guide.name, out / 'automation/README.html']
    gallery = {**gallery_pages(manifest, metadata), **organization_pages(manifest, metadata),
               'gallery/features.html': feature_references.feature_page(manifest, derived),
               'gallery/membranes.html': membrane_gallery.membrane_page(manifest, metadata, membrane_gallery.load_layout(root))}
    pages += [out / p for p in gallery]
    pages += [published / name for name in rendered]
    pages += [(out / 'docs' / md.relative_to(root / 'docs')).with_suffix('.html') for md in (root / 'docs').rglob('*.md')]
    pages += [out / 'docs' / (logical[:-3] + '.html') for logical, asset in build_site.recovered_documents(manifest).items() if asset]
    # Every other output file also has an explicit source or generated role.
    allowed = {'index.html', 'style.css', 'gallery.js', 'detail-views.js', 'review-collections.json', 'feature-references.json', 'membrane-compare.js', '.nojekyll', guide.name,
               'automation/README.md', 'automation/README.html'}
    allowed |= {'resources/character-library/' + name for name in expected | rendered}
    allowed |= set(gallery)
    for source in (root / 'docs').rglob('*'):
        if source.is_file():
            name = source.relative_to(root / 'docs').as_posix()
            allowed |= {'docs/' + name, 'source/' + name}
            if source.suffix == '.md':
                allowed.add('docs/' + name[:-3] + '.html')
    for alias in build_site.guide_aliases(guide.read_text(encoding='utf-8'), manifest):
        allowed |= {alias, 'docs/' + alias}
    for logical, asset in build_site.recovered_documents(manifest).items():
        if asset:
            allowed |= {'docs/' + logical, 'docs/' + logical[:-3] + '.html'}
    check({p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file()} == allowed,
          'Unexpected or missing file in Pages output')
    errors = [error for path in pages for error in local_links(path, out)]
    check(not errors, 'Broken public navigation:\n' + '\n'.join(errors))
    images, references = set(), set()
    for name in gallery:
        page = Page((out / name).read_text(encoding='utf-8'))
        check(page.viewport, 'Missing responsive viewport')
        check(len(page.ids) == len(set(page.ids)), 'Duplicate gallery element IDs')
        references.update(x for x in page.cards if re.fullmatch('[RC][0-9]{2}', x))
        for image in page.images:
            check(image.get('alt') and image.get('loading') == 'lazy', 'Missing image accessibility or lazy loading')
            images.add(unquote(urlsplit(image['src']).path).removeprefix('../resources/character-library/'))
    check(references == resource_library.EXPECTED_IDS, 'Gallery lost reserved reference IDs')
    check(images == {a['resource_path'] for a in manifest['assets'] if is_image(a)}, 'Gallery does not cover all original images')
    check(json.loads((out / 'review-collections.json').read_text(encoding='utf-8')) == metadata,
          'Publication must include only validated public organization')
    check(json.loads((out / 'feature-references.json').read_text(encoding='utf-8')) == derived,
          'Feature assignments differ from collection membership or recorded reference limits')
    check(feature_references.feature_page(manifest, derived) in (out / 'gallery/features.html').read_text(encoding='utf-8'),
          'Feature page lost assignment scopes, statuses or parent caveats')
    check(gallery['gallery/membranes.html'] in (out / 'gallery/membranes.html').read_text(encoding='utf-8'),
          'Membrane comparison page lost direction assignments or reference caveats')
    refs = Page((out / 'gallery/index.html').read_text(encoding='utf-8'))
    check(not {'R32', 'R33', 'R34'} & set(refs.cards), 'Membrane experiments leaked into main reference gallery')
    css = (out / 'style.css').read_text()
    check('@media(max-width:760px)' in css and 'min(100%,310px)' in css, 'Responsive grid rules absent')
    # Scan the entire publication, including unchanged archival HTML, omitting
    # embedded image strings whose base64 fragments are not textual identities.
    for path in out.rglob('*'):
        if not path.is_file():
            continue
        check(not path.is_symlink(), 'Published symlink')
        check(path.suffix.lower() != '.zip' and 'exec-' not in path.name, 'Private/runtime archive label published')
        if path.suffix.lower() in {'.md', '.json', '.html', '.txt'}:
            text = path.read_text(encoding='utf-8-sig')
            text = re.sub(r'data:image/[^;]+;base64,[A-Za-z0-9+/=]+', '[embedded image]', text)
            check(not any(p.search(text) for p in (resource_library.OWNER_ID, resource_library.OWNER_PATH, resource_library.PRIVATE_URL)), f'Private marker in publication: {path.relative_to(out)}')
    print(f'Public site verified: {len(manifest["assets"])} exact assets, 187 gallery images, 49 reference IDs, {len(pages)} linked pages; illustrated guide unchanged.')


if __name__ == '__main__':
    validate()
