"""Static gallery views. Registry text is escaped and never promoted to canon."""
import html
from pathlib import Path
from urllib.parse import quote


def esc(value):
    return html.escape(str(value), quote=True)


def url(path):
    return quote(path, safe="/#")


def is_image(asset):
    return Path(asset["stored_filename"]).suffix.lower() in {".png", ".jpg", ".gif"}


def is_experiment(asset):
    return any("experiment" in label for label in asset["classification"])


def image_url(asset, prefix="../"):
    return url(prefix + "resources/character-library/" + asset["resource_path"])


def wrap(title, body, prefix="", gallery=False):
    nav = (("Overview", "index.html"), ("Reference gallery", "gallery/index.html"),
           ("Collections", "gallery/collections.html"), ("By feature", "gallery/features.html"),
           ("Archive", "gallery/archive.html"),
           ("Experiments", "gallery/experiments.html"), ("Compare membranes", "gallery/membranes.html"),
           ("All artwork", "gallery/artwork.html"),
           ("Illustrated guide", "Myca Resource Guide.html"),
           ("Written design", "docs/Myca Character Design Brief.html"))
    links = "".join(f'<a href="{url(prefix + path)}">{label}</a>' for label, path in nav)
    script = f'<script src="{url(prefix + "gallery.js")}" defer></script>' if gallery else ""
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(title)} · Myca Cellium</title><link rel="stylesheet" href="{url(prefix + "style.css")}">{script}'
            '</head><body><a class="skip" href="#main">Skip to content</a><header class="site-header">'
            f'<a class="wordmark" href="{url(prefix + "index.html")}">MYCA <span>CELLIUM</span></a>'
            f'<nav aria-label="Main navigation">{links}</nav></header>'
            f'<main id="main">{body}</main><footer>Character continuity first. '
            'Written rules govern; artwork controls only its documented feature scope.</footer></body></html>')


def original_link(asset):
    return f'<a class="original" href="{image_url(asset)}">Open original <span aria-hidden="true">↗</span></a>'


def picture(asset, alt):
    return (f'<a class="image-link" href="{image_url(asset)}" aria-label="{esc("Open original: " + alt)}">'
            f'<img src="{image_url(asset)}" alt="{esc(alt)}" loading="lazy" decoding="async"></a>')


def card(asset, reference=None):
    registry = reference["design_registry"] if reference else None
    rid = reference["reference_id"] if reference else ""
    title = registry["title"] if registry else asset["stored_filename"]
    status = (registry.get("status") or "Exact detail crop; inherits parent limitations.") if registry else "; ".join(asset["classification"])
    group = "crop" if rid.startswith("C") else "source" if rid else "other"
    if not reference:
        group = "production" if "pet-production" in asset["classification"] else "cosplay" if "cosplay inspiration" in asset["classification"] else "other"
    identity = rid or "asset-" + asset["sha256"][:16]
    search = " ".join([rid, title, status, *asset["filename_aliases"], *asset["classification"],
                       registry.get("approved_scope", "") or "" if registry else "",
                       registry.get("known_defects", "") or "" if registry else ""])
    body = f'<p class="eyebrow">{esc(rid or "Unregistered artwork")}</p><h2>{esc(title)}</h2>'
    body += f'<p class="status">{esc(status)}</p>'
    if registry:
        scope = registry.get("crop_scope") if rid.startswith("C") else registry.get("approved_scope")
        body += f'<div class="scope"><h3>{"Crop scope and inherited caveat" if rid.startswith("C") else "Feature-specific use scope"}</h3><p>{esc(scope or "No new approval recorded.")}</p></div>'
        if registry.get("known_defects"):
            body += f'<div class="caveat"><h3>Do not inherit</h3><p>{esc(registry["known_defects"])}</p></div>'
        if rid.startswith("C"):
            crop = reference["crop"]
            body += f'<p class="crop-meta">Parent {esc(crop["parent_reference_id"])} · bounds {esc(crop["bounds_px"])} · {esc(crop["size_px"])} px. Right and bottom edges are exclusive. Exact original crop; no corrections.</p>'
    else:
        body += '<p class="scope">No reference identifier or new feature approval is assigned. Use the current written design and registry limitations.</p>'
    body += original_link(asset)
    body += '<details><summary>Integrity and file labels</summary>'
    body += f'<p class="hash">SHA-256 <code>{asset["sha256"]}</code></p><p>{asset["size_bytes"]:,} bytes · unchanged original</p>'
    body += f'<p>{esc("; ".join(asset["filename_aliases"]))}</p></details>'
    return (f'<article id="{identity}" class="asset-card" data-card data-kind="{group}" data-search="{esc(search.lower())}">'
            + picture(asset, title) + '<div class="card-body">' + body + '</div></article>')


def missing_card(reference):
    rid = reference["reference_id"]
    registry = reference["design_registry"]
    return (f'<article id="{rid}" class="asset-card missing" data-card data-kind="missing" data-search="{esc((rid + " " + registry["title"]).lower())}">'
            '<div class="missing-image">No verified image</div><div class="card-body">'
            f'<p class="eyebrow">{rid}</p><h2>{esc(registry["title"])}</h2><p class="status">Missing or unmapped · identifier reserved</p>'
            f'<h3>Recorded scope</h3><p>{esc(registry.get("approved_scope", "No new approval recorded."))}</p>'
            '<p>No substitute image has been assigned.</p></div></article>')


def controls(options, count):
    choices = '<option value="all">All on this page</option>' + ''.join(f'<option value="{value}">{label}</option>' for value, label in options)
    return ('<form class="filters" role="search"><div><label for="gallery-search">Search artwork, IDs or scope</label>'
            '<input id="gallery-search" type="search" placeholder="Try R08, lichen, contact…" autocomplete="off"></div>'
            f'<div><label for="gallery-kind">Show</label><select id="gallery-kind">{choices}</select></div>'
            '<button type="reset">Reset</button></form>'
            f'<p id="gallery-count" class="result-count" aria-live="polite">{count} items on this page</p>'
            '<p id="gallery-empty" hidden>No matching artwork. Try another word or reset the filters.</p>')


def gallery_pages(manifest, metadata=None):
    assets = {a["sha256"]: a for a in manifest["assets"]}
    archived = set((metadata or {}).get("archived", []))
    registered = {sha for ref in manifest["references"] for sha in ref["asset_sha256"]}
    references, experimental_refs = [], []
    for ref in manifest["references"]:
        if not ref["asset_sha256"]:
            references.append(missing_card(ref))
        else:
            asset = assets[ref["asset_sha256"][0]]
            if asset["sha256"] in archived:
                continue
            (experimental_refs if is_experiment(asset) else references).append(card(asset, ref))
    other = sorted((a for a in assets.values() if is_image(a) and a["sha256"] not in registered
                    and a["sha256"] not in archived), key=lambda a: a["stored_filename"].casefold())
    membrane = [card(a) for a in other if "experimental membrane design" in a["classification"]]
    experiments = [card(a) for a in other if is_experiment(a) and "experimental membrane design" not in a["classification"]]
    supporting = [card(a) for a in other if not is_experiment(a)]
    tabs = '<nav class="gallery-tabs" aria-label="Gallery sections"><a href="index.html">Scoped references</a><a href="experiments.html">Experiments</a><a href="artwork.html">Supporting artwork</a><a href="../resources/character-library/Asset-Catalog.html">Full asset catalog</a></nav>'
    intro = '<p class="kicker">Recovered character library</p><h1>Feature-scoped references</h1><p class="lede">Source images and exact detail crops, with their recorded use scopes and limitations.</p>'
    intro += '<p class="notice">No complete generated sheet is fully canonical. A reference may support one feature and contradict another. The current written rules resolve conflicts. These recorded use scopes do not grant new approval.</p>'
    intro += tabs + controls([("source", "Source references"), ("crop", "Detail crops"), ("missing", "Missing IDs")], len(references))
    refs_body = intro + '<div class="gallery-grid">' + ''.join(references) + '</div>'
    ex_body = '<p class="kicker">Experimental archive</p><h1>Fungal membrane experiments</h1><p class="lede">Candidate designs, preserved for comparison.</p><p class="notice experiment-notice">The dusty-pink flared skirt and dark-brown waistband remain the baseline. Membrane candidates are experiments, not a selected canon replacement. During membrane tasks, follow the written rules: no belt, waistband, fastening or ordinary fabric attachment seam.</p>'
    ex_body += '<p><a class="button" href="membranes.html">Separate directions and compare studies</a></p>'
    ex_body += tabs + controls([], len(experimental_refs) + len(membrane) + len(experiments))
    ex_body += '<section><h2>Registered membrane studies · R32–R34</h2><div class="gallery-grid">' + ''.join(experimental_refs) + '</div></section>'
    ex_body += '<section><h2>Other membrane candidates</h2><p>Unregistered studies do not create R35 or a new canon entry.</p><div class="gallery-grid">' + ''.join(membrane) + '</div></section>'
    ex_body += '<section><h2>Other experimental visual studies</h2><div class="gallery-grid">' + ''.join(experiments) + '</div></section>'
    art_body = '<p class="kicker">Supporting archive</p><h1>More original artwork</h1><p class="lede">Animation, production, cosplay inspiration and historical studies.</p><p class="notice">Archive inclusion and filenames such as “canonical” do not approve a whole image. These unregistered assets inherit no new reference ID or canon status.</p>'
    art_body += tabs + controls([("production", "Animation and production"), ("cosplay", "Cosplay inspiration"), ("other", "Other supporting artwork")], len(supporting))
    art_body += '<div class="gallery-grid">' + ''.join(supporting) + '</div>'
    return {"gallery/index.html": refs_body, "gallery/experiments.html": ex_body, "gallery/artwork.html": art_body}


def overview(manifest):
    assets = {a["sha256"]: a for a in manifest["assets"]}
    ref = next(r for r in manifest["references"] if r["reference_id"] == "R30")
    hero = assets[ref["asset_sha256"][0]]
    body = '<section class="hero"><div><p class="kicker">A living fungal character · design baseline 1.0</p><h1>Myca’s reference library</h1><p class="lede">Explore the original artwork, precise feature references and evolving design studies.</p><p>Written design rules remain authoritative. Reference art supports only its documented features.</p><div class="actions"><a class="button" href="gallery/features.html">Browse by feature</a><a href="gallery/index.html">All registered references</a><a href="Myca%20Resource%20Guide.html">Open illustrated guide ↗</a></div></div>'
    body += f'<figure><img src="{image_url(hero, "")}" alt="R30 soft-shaded three-pose supporting reference" decoding="async"><figcaption>R30 · supporting style and pose reference. No whole-sheet approval.</figcaption></figure></section>'
    body += '<section class="stats" aria-label="Recovered library coverage">' + ''.join(f'<div><strong>{number}</strong><span>{label}</span></div>' for number, label in [(187, "original image files"), (46, "recovered reference IDs"), (15, "pixel-exact detail crops"), (234, "public assets")]) + '</section>'
    body += '<section class="overview-grid"><article><p class="kicker">Use deliberately</p><h2>References with boundaries</h2><p>Read the intended feature scope beside each image, including corrections and defects that must not be inherited.</p><a href="gallery/index.html">Open scoped references →</a></article><article class="experiment-panel"><p class="kicker">Separate from canon</p><h2>Living-membrane candidates</h2><p>The pink skirt and dark waistband remain the baseline. Explore retained membrane studies as experimental alternatives.</p><a href="gallery/experiments.html">Review experiments →</a></article><article><p class="kicker">Development archive</p><h2>Animation and other artwork</h2><p>Original production frames, studies and inspiration, with recorded classifications and SHA-256 fingerprints.</p><a href="gallery/artwork.html">Browse supporting artwork →</a></article></section>'
    docs = [("Character Design Brief", "Myca Character Design Brief.html"), ("Master Character Prompt", "Myca Master Character Prompt.html"), ("Locomotion Reference", "Myca Locomotion Reference.html"), ("Prompt Modules", "Production/Prompt Modules and Style Translation.html"), ("Reference Index", "References/Reference Index.html"), ("Canon Shortlist · recommendation", "References/Definitive Canon Shortlist.html"), ("Expression and Acting Guide · historical snapshot", "Myca Expression and Acting Guide.html")]
    body += '<section class="page"><h2>Written authority and documentation</h2><ul class="doc-links">' + ''.join(f'<li><a href="{url("docs/" + path)}">{esc(label)}</a></li>' for label, path in docs) + '</ul><p><a href="resources/character-library/Asset-Catalog.html">All public assets and document versions</a> · <a href="resources/character-library/Index.html">Full reference scopes</a></p></section>'
    body += '<section class="page"><h2>Recovery coverage</h2><p>The recovered library is available here, including the original images, crops, acting guide, review checklists, decision-log snapshots and S01–S03 source documents. Historical documents are snapshots, not new canon authority.</p><p class="notice">Remaining gaps: R24, R25 and R26 are missing or unmapped. Eight previously listed binaries remain unavailable (one MP4 and seven production ZIPs). No replacement assets or filenames have been invented.</p><p><a href="resources/character-library/Missing-Resources.json">Missing-resource records</a> · <a href="resources/character-library/Sanitation-Report.html">Sanitation and preservation report</a> · <a href="resources/character-library/SHA256SUMS">Checksum ledger</a></p></section>'
    return body
