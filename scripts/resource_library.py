#!/usr/bin/env python3
"""Validate public originals and labeled metadata derivatives; build navigation."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import quote
from windows_paths import path_errors, validate_repository

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "resources/character-library"
EXPECTED_HASHES = {
    "SHA256SUMS": "2c3c48fbae29a08e343bb631568a06f9716673bd4aecf64bb54dc001e3e73fde",
    "manifest.json": "fc5ff117f22bf5bd1ee6caaaaf06c79a6efdcb2c5ef82415496de0af1474ba20",
}
EXPECTED_IDS = {f"R{i:02}" for i in range(1, 35)} | {f"C{i:02}" for i in range(1, 16)}
MISSING_IDS = {"R24", "R25", "R26"}
SANITIZED_SOURCES = {'9e2c429e01e45b75be37350f68bd83cd723f1120af8745e7abb16ef4fb34dd18', '940af9d0141022ac5e7aa1ad5e6e5bcd10323c98e9066cf27fe128fa69993450'}
OWNER_ID = re.compile(r"\b(?:pet|page|libfile|file|link|g-p|exec)[_-][0-9a-f-]{16,}\b")
OWNER_PATH = re.compile(r"(?i)(?:[A-Z]:\\+(?:Users|projects)\\|/(?:mnt/data|workspace|home|Users)/)")
PRIVATE_URL = re.compile(r"https?://[^\s\"<>]*(?:chatgpt\.com/(?:c|g|share)|oaiusercontent|blob\.core|amazonaws|[?&](?:sig|token|X-Amz-))")
CROP = re.compile(
    r"\*\*Parent:\*\* (R\d{2})\. \*\*Crop:\*\* "
    r"`\((\d+), (\d+), (\d+), (\d+)\)`\. "
    r"\*\*Size:\*\* (\d+) × (\d+) pixels"
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def local_path(relative):
    require(isinstance(relative, str) and bool(relative), "Empty resource path")
    require(not relative.startswith(("/", "-")) and "\\" not in relative
            and all(part not in {"", ".", ".."} for part in relative.split("/")),
            f"Unsafe resource path: {relative}")
    require(not path_errors([relative]), f"Windows-incompatible resource path: {relative}")
    path = LIBRARY / relative
    require(path.resolve().is_relative_to(LIBRARY.resolve()), f"Escaping path: {relative}")
    require(not path.is_symlink() and path.is_file(), f"Missing regular file: {relative}")
    return path


def load_manifest():
    for name, sha in EXPECTED_HASHES.items():
        require(digest(local_path(name)) == sha, f"Reviewed snapshot changed: {name}")
    manifest = json.loads((LIBRARY / "manifest.json").read_text(encoding="utf-8"))
    require(manifest["schema_version"] == "1.0", "Unexpected manifest schema")
    return manifest


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def link(asset):
    return f"[{cell(asset['stored_filename'])}]({quote(asset['resource_path'], safe='/')})"


def group(asset):
    classes = asset["classification"]
    if "experimental membrane design" in classes:
        return "Living-membrane experiments"
    if any("experimental" in item for item in classes):
        return "Other experimental studies"
    if "pet-production" in classes:
        return "Pet and animation production"
    if "cosplay inspiration" in classes:
        return "Cosplay inspiration"
    return "Supporting references and historical documents"


def rendered_indexes(manifest):
    assets = {asset["sha256"]: asset for asset in manifest["assets"]}
    refs = manifest["references"]
    originals = sum(asset["original_bytes"] is True for asset in assets.values())
    derivatives = len(assets) - originals
    aliases = sum(len(asset["filename_aliases"]) for asset in assets.values())
    index = [
        "# Recovered Myca character library", "",
        f"{len(assets)} public assets: {originals} unchanged originals and {derivatives} "
        f"clearly labeled sanitized metadata derivatives, with {aliases} current filename aliases. "
        "46 of 49 reference IDs are recovered; R24–R26 remain missing or unmapped. "
        "The 15 detail crops match their recorded parent pixels. Inclusion is not whole-image approval.", "",
        "[All assets and filename aliases](Asset-Catalog.md) · "
        "[Separate membrane experiments](Experiments.md) · "
        "[Design history](Design-History.md) · [Coverage and validation](Recovery-Notes.md) · "
        "[Missing-resource records](Missing-Resources.json) · "
        "[Public recovery manifest](manifest.json)", "",
        "The [current character brief](../../docs/Myca%20Character%20Design%20Brief.md), "
        "[locomotion rules](../../docs/Myca%20Locomotion%20Reference.md), "
        "[reference index](../../docs/References/Reference%20Index.md), and "
        "[approval protocol](../../automation/README.md) remain authoritative. "
        "Historical documents retain their original bytes except for the two explicitly labeled "
        "sanitized metadata derivatives; their unchanged sources remain in the owner archive. The manifest field "
        "`approved_scope` reproduces the registry's **Use for** guidance; it does not authenticate a new approval.", "",
        "## Source references and history", "",
        "| ID | Reference | Recovery | Registry status |", "|---|---|---|---|",
    ]
    for ref in refs:
        if not ref["reference_id"].startswith("R"):
            continue
        registry = ref["design_registry"]
        title = cell(registry["title"])
        if ref["asset_sha256"]:
            asset = assets[ref["asset_sha256"][0]]
            title = f"[{title}]({quote(asset['resource_path'], safe='/')})"
        index.append(f"| {ref['reference_id']} | {title} | {ref['status']} | {cell(registry['status'])} |")
    index += ["", "## Feature scope and defects", ""]
    for ref in refs:
        registry = ref["design_registry"]
        index += [f"### {ref['reference_id']} · {registry['title']}", ""]
        if ref["asset_sha256"]:
            index += ["Original bytes: " + ", ".join(link(assets[sha]) for sha in ref["asset_sha256"]), ""]
        else:
            index += ["**Missing or unmapped.** The identifier remains reserved; no similar-looking image is assigned to it.", ""]
        if ref["reference_id"].startswith("C"):
            crop = ref["crop"]
            bounds = ', '.join(map(str, crop["bounds_px"]))
            width, height = crop["size_px"]
            index += [f"**Parent:** {crop['parent_reference_id']}. **Bounds:** `({bounds})` "
                      f"with exclusive right/bottom edges. **Size:** {width} × {height} pixels.", "",
                      "**Scope and inherited caveat:** " + registry["crop_scope"], ""]
        else:
            index += ["**Registry status:** " + registry["status"], "",
                      "**Use for:** " + registry.get("approved_scope", "No new approval recorded."), ""]
            if registry.get("known_defects"):
                index += ["**Do not inherit:** " + registry["known_defects"], ""]
            if registry.get("original"):
                index += ["**Registry original filename and dimensions:** " + registry["original"], ""]

    catalog = ["# Public assets and aliases", "",
               "[Reference IDs and feature caveats](Index.md) · [Membrane experiments](Experiments.md)", "",
               "Links open unchanged originals or explicitly labeled sanitized metadata derivatives. "
               "Derivatives are not byte-identical aliases of their sources; source hashes and retired labels "
               "are recorded separately in the manifest. Distinct hashes remain distinct, even when names or "
               "compositions resemble one another. An unavailable original filename is reported as unknown; "
               "the stored name is a Page label in those cases. A recovered filename containing “canonical” "
               "does not approve the complete design.", ""]
    for category in ("Supporting references and historical documents", "Pet and animation production",
                     "Living-membrane experiments", "Other experimental studies", "Cosplay inspiration"):
        selected = sorted((a for a in assets.values() if group(a) == category),
                          key=lambda a: (a["stored_filename"].casefold(), a["sha256"]))
        catalog += [f"## {category} · {len(selected)} assets", "",
                    "| Asset | Kind | Original filename | Current aliases | Classification | SHA-256 |",
                    "|---|---|---|---|---|---|"]
        for asset in selected:
            kind = "Unchanged original" if asset["original_bytes"] else "Sanitized metadata derivative"
            original = ("Withheld runtime label; unchanged bytes" if asset.get("original_filename_status") == "withheld_runtime_identifier" else (asset["original_filename"] or "Unknown; Page label only")) if asset["original_bytes"] else "Not an original"
            catalog.append(f"| {link(asset)} | {kind} | {cell(original)} | {cell('; '.join(asset['filename_aliases']))} | "
                           f"{cell('; '.join(asset['classification']))} | `{asset['sha256']}` |")
        catalog.append("")

    experiments = ["# Living-membrane experiments", "",
                   "[Reference library](Index.md) · [All public assets](Asset-Catalog.md) · [Design history](Design-History.md)", "",
                   "The dusty-pink flared skirt and dark-brown waistband remain the baseline. "
                   "These membrane images are experiments, including the later unindexed lily/pencil-skirt exploration. "
                   "They do not create R35 or a canon replacement. Follow the current written membrane rules "
                   "for a membrane task, with no belt, waistband, fastening, or ordinary fabric attachment seam.", "",
                   "R32, R33 and R34 retain their individual registry scopes and defects in the "
                   "[reference library](Index.md). R32 and R34 share an earlier original basename but "
                   "have different SHA-256 values and are separately preserved.", "",
                   "| Original bytes | Existing classification | SHA-256 |", "|---|---|---|"]
    for asset in sorted((a for a in assets.values() if group(a) == "Living-membrane experiments"),
                        key=lambda a: (a["stored_filename"].casefold(), a["sha256"])):
        experiments.append(f"| {link(asset)} | {cell('; '.join(asset['classification']))} | `{asset['sha256']}` |")
    experiments.append("")
    return {"Index.md": "\n".join(index), "Asset-Catalog.md": "\n".join(catalog),
            "Experiments.md": "\n".join(experiments)}


def validate(manifest, images=False):
    validate_repository(ROOT)
    checksums = {}
    for line in (LIBRARY / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", line)
        require(match is not None, "Invalid checksum entry")
        sha, name = match.groups()
        require(name not in checksums, f"Duplicate checksum path: {name}")
        require(digest(local_path(name)) == sha, f"Checksum failed: {name}")
        checksums[name] = sha
    require(len(checksums) == 237, "Recovery snapshot must retain 237 checksum entries")
    require(set(checksums) == {"manifest.json", "README.md", "Design-History.md"}
            | {a["resource_path"] for a in manifest["assets"]}, "Checksum coverage differs from manifest")
    assets = {}
    for asset in manifest["assets"]:
        sha = asset["sha256"]
        require(sha not in assets, f"Duplicate byte object: {sha}")
        assets[sha] = asset
        path = local_path(asset["resource_path"])
        require(path.stat().st_size == asset["size_bytes"], f"Size differs: {path.name}")
        require(checksums[asset["resource_path"]] == sha, f"Manifest hash differs: {path.name}")
        require(type(asset["original_bytes"]) is bool, f"Missing explicit original/derivative status: {path.name}")
        require(asset["resource_path"] == f"resources/{sha[:16]}/{asset['stored_filename']}",
                f"Hash directory or filename differs: {path.name}")
        require(path.stat().st_size < 100 * 1024 * 1024, f"File requires storage outside regular Git: {path.name}")
        require(path.suffix.lower() != ".zip", "Nested archives must remain outside Git")
        require(asset["classification"] and asset["filename_aliases"], f"Missing metadata: {path.name}")
        require(asset["original_filename"] is None or asset["original_filename"] in asset["filename_aliases"],
                f"Original filename is not retained as an alias: {path.name}")
    require(len(assets) == 234 and sum(a["size_bytes"] for a in assets.values()) == 421015862,
            "Reviewed asset count or byte total differs")
    original_assets = [a for a in assets.values() if a["original_bytes"]]
    derivatives = [a for a in assets.values() if not a["original_bytes"]]
    require(len(original_assets) == 232 and len(derivatives) == 2,
            "Public resources must distinguish 232 unchanged originals from 2 sanitized derivatives")
    require({a.get("derivation", {}).get("source_sha256") for a in derivatives} == SANITIZED_SOURCES,
            "Unexpected sanitized source or missing provenance")
    exclusions = {item["sha256"] for item in manifest["public_subset_exclusions"]}
    require(SANITIZED_SOURCES <= exclusions and not SANITIZED_SOURCES & assets.keys(),
            "Unsanitized metadata sources must be excluded from the current public assets")
    require(not exclusions & assets.keys(), "An excluded original remains in the public asset set")
    for asset in derivatives:
        require("sanitized metadata derivative" in asset["classification"]
                and "_SANITIZED." in asset["stored_filename"]
                and asset["derivation"]["kind"] == "sanitized_public_metadata_derivative",
                "Metadata derivatives must be clearly labeled")
        path = LIBRARY / asset["resource_path"]
        if path.suffix == ".json":
            report = json.loads(path.read_text(encoding="utf-8"))
            require(report["document_kind"] == "sanitized_public_derivative",
                    "JSON derivative lacks its public notice")
            if "45_Myca" in path.name:
                require("pet" not in report and "active_pet" not in report and "library" not in report
                        and "creation_verified_by" not in report,
                        "Private service or selection metadata remains")
        else:
            require("Sanitized derivative, not an unchanged original." in path.read_text(encoding="utf-8"),
                    "Text derivative lacks its public notice")
    for asset in assets.values():
        path = LIBRARY / asset["resource_path"]
        if path.suffix.lower() in {".md", ".json", ".html", ".txt", ".py", ".yml"}:
            require(not OWNER_ID.search(path.read_text(encoding="utf-8-sig")),
                    f"Owner-specific service identifier in public resource: {path.name}")
    # Scan both asset bodies and envelope manifests/navigation. Ignore embedded
    # image payload strings: random base64 fragments are not textual identities.
    for path in LIBRARY.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".md", ".json", ".html", ".txt", ".py", ".yml"}:
            content = path.read_text(encoding="utf-8-sig")
            content = re.sub(r"data:image/[^;]+;base64,[A-Za-z0-9+/=]+", "[embedded image]", content)
            require(not any(pattern.search(content) for pattern in (OWNER_ID, OWNER_PATH, PRIVATE_URL)),
                    f"Private identifier, owner path or private URL remains: {path.name}")
    actual = {p.relative_to(LIBRARY).as_posix() for p in (LIBRARY / "resources").rglob("*") if p.is_file()}
    require(actual == {a["resource_path"] for a in assets.values()}, "Unexpected or missing asset files")
    refs = {r["reference_id"]: r for r in manifest["references"]}
    require(len(refs) == len(manifest["references"]) and set(refs) == EXPECTED_IDS,
            "Reference IDs must retain R01–R34 and C01–C15 exactly once")
    for ref in refs.values():
        require(set(ref["design_registry"]) <= {
            "reference_id", "title", "status", "approved_scope", "known_defects",
            "original", "crop_parent", "crop_scope"
        }, "Private source-context field in public registry")
    for rid, ref in refs.items():
        require(ref["design_registry"]["reference_id"] == rid, f"Registry identity differs: {rid}")
        require(ref["status"] == ("missing_or_unmapped" if rid in MISSING_IDS else "recovered"),
                f"Recovery state differs: {rid}")
        require(len(ref["asset_sha256"]) == (0 if rid in MISSING_IDS else 1), f"Asset mapping differs: {rid}")
        require(all(sha in assets for sha in ref["asset_sha256"]), f"Missing mapped bytes: {rid}")
        require(all(assets[sha]["original_bytes"] for sha in ref["asset_sha256"]),
                f"An image reference cannot be substituted with a derivative: {rid}")
    require(refs["R32"]["asset_sha256"] != refs["R34"]["asset_sha256"], "R32 and R34 must remain distinct")
    for rid in ("R32", "R33", "R34"):
        require("Experimental" in refs[rid]["design_registry"]["status"], f"Promoted membrane reference: {rid}")
        require("experimental membrane design" in assets[refs[rid]["asset_sha256"][0]]["classification"],
                f"Missing experimental classification: {rid}")
    for name, expected in rendered_indexes(manifest).items():
        require(local_path(name).read_text(encoding="utf-8") == expected, f"Navigation is stale: {name}")
    from urllib.parse import unquote, urlsplit
    for name in ("Index.md", "Asset-Catalog.md", "Experiments.md", "Recovery-Notes.md", "Sanitation-Report.md", "README.md"):
        for target in re.findall(r"\]\(([^)]+)\)", local_path(name).read_text(encoding="utf-8")):
            url = urlsplit(target)
            if url.scheme or not url.path:
                continue
            resolved = (LIBRARY / unquote(url.path)).resolve()
            require(resolved.is_relative_to(ROOT.resolve()) and resolved.is_file(),
                    f"Broken or escaping navigation link in {name}")
    missing = json.loads(local_path("Missing-Resources.json").read_text(encoding="utf-8"))
    require(set(missing["missing_or_unmapped_reference_ids"]) == MISSING_IDS, "Missing reference reservations differ")
    gaps = missing["unavailable_page_binary_records"]
    require(len(gaps) == 8 and {g["label"] for g in gaps}
            == {"All animations MP4"} | {f"Production files {i} of 7" for i in range(1, 8)},
            "Eight unavailable Page binary labels must remain present")
    for gap in gaps:
        require(gap["status"] == "unavailable" and gap["original_filename"] is None,
                "Do not claim missing Page bytes or infer filenames")
        require(gap["mime_type"] == ("video/mp4" if gap["label"] == "All animations MP4" else "application/zip")
                and type(gap["reported_size_bytes"]) is int and gap["reported_size_bytes"] > 0,
                "Missing Page source metadata differs")
    if images:
        from PIL import Image
        for asset in assets.values():
            path = LIBRARY / asset["resource_path"]
            if path.suffix.lower() not in {".png", ".jpg", ".gif"}:
                continue
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                for frame in range(getattr(image, "n_frames", 1)):
                    image.seek(frame)
                    image.load()
        for rid, ref in refs.items():
            if not rid.startswith("C"):
                continue
            crop = ref["crop"]
            require(crop["edges"] == "exclusive right/bottom", f"Invalid crop convention: {rid}")
            parent = refs[crop["parent_reference_id"]]
            bounds = tuple(crop["bounds_px"])
            with Image.open(LIBRARY / assets[parent["asset_sha256"][0]]["resource_path"]) as original, \
                 Image.open(LIBRARY / assets[ref["asset_sha256"][0]]["resource_path"]) as detail:
                require(0 <= bounds[0] < bounds[2] <= original.width
                        and 0 <= bounds[1] < bounds[3] <= original.height, f"Invalid crop bounds: {rid}")
                require(detail.size == tuple(crop["size_px"]), f"Crop size differs: {rid}")
                require(original.crop(bounds).convert("RGBA").tobytes() == detail.convert("RGBA").tobytes(),
                        f"Crop pixels differ from parent: {rid}")
    print("Verified 237 checksums; 232 unchanged originals + 2 labeled sanitized derivatives; 49 reference records (46 recovered, 3 missing); 8 Page binary gaps.")
    if images:
        print("All 187 image files decode; all 15 crops match their parent pixels. No image bytes were written.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("validate", "build-indexes"))
    parser.add_argument("--images", action="store_true", help="Also decode images and compare crop pixels; requires Pillow")
    args = parser.parse_args()
    try:
        manifest = load_manifest()
        if args.action == "build-indexes":
            for name, text in rendered_indexes(manifest).items():
                (LIBRARY / name).write_text(text, encoding="utf-8")
            print("Built Index.md, Asset-Catalog.md, and Experiments.md without changing the recovery snapshot.")
        else:
            validate(manifest, images=args.images)
    except (ValueError, KeyError, OSError, ImportError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
