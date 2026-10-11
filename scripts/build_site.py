#!/usr/bin/env python3
"""Build Pages from written authority and the verified public library."""
import html
from pathlib import Path
import posixpath
import re
import shutil
from urllib.parse import quote, unquote, urlsplit

import resource_library
import review_metadata
from review_public import organization_pages
from site_gallery import gallery_pages, overview, wrap

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '_site'
PUBLIC_PAGES = ('Index.md', 'Asset-Catalog.md', 'Experiments.md', 'README.md',
                'Design-History.md', 'Recovery-Notes.md', 'Sanitation-Report.md')
PUBLIC_METADATA = ('manifest.json', 'SHA256SUMS', 'Missing-Resources.json')
RECOVERED_DOCS = {
    'Myca Expression and Acting Guide.md': 'Myca Expression and Acting Guide.md',
    'Production/Model Sheets and Review Checklist.md': 'Model Sheets and Review Checklist.md',
    'Maintenance/Decision Log and Open Questions.md': 'Decision Log and Open Questions.md',
    **{f'Archive/Previous Documents/S0{i} Previous {name}.md':
       f'S0{i} Previous {name}.md' for i, name in enumerate(
           ('Character Design Brief', 'Master Character Prompt', 'Locomotion Reference'), 1)},
}


def public_files(manifest, metadata=None):
    """An explicit allowlist; never recursively copy a recovery directory."""
    files = set(PUBLIC_PAGES + PUBLIC_METADATA) | {a['resource_path'] for a in manifest['assets']}
    if metadata:
        files |= {review_metadata.asset_relative(a, metadata) for a in manifest['assets']}
    return files


def publish_library(library, out, manifest, metadata=None):
    metadata = metadata or review_metadata.default_metadata()
    for relative in sorted(public_files(manifest, metadata)):
        source = review_metadata.locate(library, relative, manifest, metadata)
        if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(library.resolve()):
            raise ValueError(f'Unsafe public library file: {relative}')
        target = out / 'resources/character-library' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)  # Preserve bytes, including historical CRLF.


def asset_aliases(manifest):
    aliases = {}
    for asset in manifest['assets']:
        for name in asset['filename_aliases']:
            aliases.setdefault(name, []).append(asset)
    return aliases


def recovered_documents(manifest):
    aliases = asset_aliases(manifest)
    # Different historical versions are not silently selected as current authority.
    return {path: aliases[label][0] if len(aliases[label]) == 1 else None
            for path, label in RECOVERED_DOCS.items() if label in aliases}


def guide_aliases(guide, manifest):
    """Verified compatibility paths keep the untouched illustrated guide usable."""
    aliases = asset_aliases(manifest)
    result = {}
    for target in re.findall(r'href="([^"]+)"', guide):
        parsed = urlsplit(html.unescape(target))
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        path = unquote(parsed.path)
        if path.startswith('/') or '..' in Path(path).parts:
            raise ValueError('Unsafe guide compatibility path')
        candidates = aliases.get(Path(path).name, [])
        if len(candidates) != 1:
            raise ValueError(f'Guide link lacks a unique verified original: {path}')
        result[path] = candidates[0]
    return result


def rewrite_links(rendered, logical_path, output_path, out, manifest, documents):
    """Resolve verified originals; ambiguous/missing labels link to the catalog."""
    aliases = asset_aliases(manifest)
    refs = {r['reference_id']: r for r in manifest['references']}
    assets = {a['sha256']: a for a in manifest['assets']}
    prefix = '../' * (len(Path(output_path).parts) - 1)

    def replacement(match):
        attr, target = match.groups()
        url = urlsplit(html.unescape(target))
        if url.scheme or url.netloc or not url.path:
            return match.group(0)
        decoded = unquote(url.path)
        logical = posixpath.normpath(posixpath.join(posixpath.dirname(logical_path), decoded))
        actual = 'docs/' + logical
        name = posixpath.basename(decoded)
        resolved = None
        if name == 'Myca Resource Guide.html':
            resolved = 'Myca Resource Guide.html'
        elif actual.endswith('.md') and (out / actual).is_file():
            resolved = actual[:-3] + '.html'
        elif (out / actual).is_file():
            resolved = actual
        elif logical in documents:
            resolved = ('docs/' + logical[:-3] + '.html') if documents[logical] else 'resources/character-library/Asset-Catalog.html'
        else:
            rid = re.match(r'([RC]\d{2})\b', name)
            if rid and rid[1] in refs and refs[rid[1]]['asset_sha256']:
                asset = assets[refs[rid[1]]['asset_sha256'][0]]
                if name in asset['filename_aliases']:
                    resolved = 'resources/character-library/' + asset['resource_path']
            if resolved is None and len(aliases.get(name, [])) == 1:
                resolved = 'resources/character-library/' + aliases[name][0]['resource_path']
            if resolved is None:
                resolved = 'resources/character-library/Asset-Catalog.html'
        suffix = ('#' + url.fragment) if url.fragment and resolved != 'resources/character-library/Asset-Catalog.html' else ''
        return f'{attr}="{quote(prefix + resolved + suffix, safe="/#")}"'

    return re.sub(r'(href|src)="([^"]+)"', replacement, rendered)


def build(root=ROOT, out=OUT, markdown=None):
    library = root / 'resources/character-library'
    # Runs inside the existing manually dispatched Pages workflow, before output.
    manifest = resource_library.load_manifest()
    resource_library.validate(manifest)
    metadata = review_metadata.load_metadata(root, manifest)
    if markdown is None:
        import mistune
        markdown = mistune.create_markdown(plugins=['table', 'strikethrough'])
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / '.nojekyll').write_text('', encoding='utf-8')
    for name in ('style.css', 'gallery.js'):
        shutil.copyfile(root / 'web' / name, out / name)
    publish_library(library, out, manifest, metadata)
    docs = root / 'docs'
    shutil.copytree(docs, out / 'docs', dirs_exist_ok=True)
    shutil.copytree(docs, out / 'source', dirs_exist_ok=True)
    # Never render, minify or rewrite the existing illustrated browser guide.
    shutil.copyfile(docs / 'Myca Resource Guide.html', out / 'Myca Resource Guide.html')
    for alias, asset in guide_aliases((docs / 'Myca Resource Guide.html').read_text(encoding='utf-8'), manifest).items():
        for prefix in ('', 'docs/'):
            dest = out / (prefix + alias)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(review_metadata.locate(library, asset['resource_path'], manifest, metadata), dest)
    documents = recovered_documents(manifest)
    for logical, asset in documents.items():
        if asset:
            dest = out / 'docs' / logical
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(review_metadata.locate(library, asset['resource_path'], manifest, metadata), dest)
    for md in (out / 'docs').rglob('*.md'):
        logical = md.relative_to(out / 'docs').as_posix()
        relative = 'docs/' + logical[:-3] + '.html'
        rendered = rewrite_links(markdown(md.read_text(encoding='utf-8')), logical, relative, out, manifest, documents)
        notice = '<p class="notice">Recovered historical document. Current written rules and feature-specific reference scopes remain authoritative.</p>' if logical in documents else ''
        (out / relative).write_text(wrap(md.stem, notice + rendered, '../' * (len(Path(relative).parts) - 1)), encoding='utf-8')
    (out / 'automation').mkdir()
    shutil.copyfile(root / 'automation/README.md', out / 'automation/README.md')
    (out / 'automation/README.html').write_text(wrap('Canon approval protocol', markdown((root / 'automation/README.md').read_text(encoding='utf-8')), '../'), encoding='utf-8')
    for name in PUBLIC_PAGES:
        relative = 'resources/character-library/' + name[:-3] + '.html'
        body = markdown((library / name).read_text(encoding='utf-8'))
        # Asset snapshots stay direct original downloads. Only navigation and
        # rendered authority pages get their .html suffix.
        def public_link(match):
            path, fragment = match.groups()
            if path.startswith('resources/'):
                return match.group(0)
            return 'href="' + path + '.html' + (fragment or '') + '"'
        body = re.sub(r'href="([^"]+)\.md(#[^"]*)?"', public_link, body)
        (out / relative).write_text(wrap(name[:-3], body, '../../'), encoding='utf-8')
    for relative, body in {**gallery_pages(manifest, metadata), **organization_pages(manifest, metadata)}.items():
        dest = out / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(wrap('Recovered gallery', body, '../', gallery=True), encoding='utf-8')
    (out / 'index.html').write_text(wrap('Character library', overview(manifest)), encoding='utf-8')
    # Explicit public schema; do not copy any local notes, journals, or desk files.
    import json
    (out / 'review-collections.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    shutil.copyfile(root / 'web/detail-views.js', out / 'detail-views.js')
    return manifest


if __name__ == '__main__':
    build()
    from validate_site import validate
    validate()
    print('Built', OUT)
