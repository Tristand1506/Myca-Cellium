#!/usr/bin/env python3
"""Validate the immutable recovery snapshot and build additive navigation."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "resources/character-library"
EXPECTED_HASHES = {
    "SHA256SUMS": "67eed825666f40b31062c14e6c3e2f3233a26f6f84e901a61a1b817139c9c1e1",
    "manifest.json": "7bf7ed6b905f941bcee1eda3ae92de3807385a3e0f2089757735ad422a5930f7",
}
EXPECTED_IDS = {f"R{i:02}" for i in range(1, 35)} | {f"C{i:02}" for i in range(1, 16)}
MISSING_IDS = {"R24", "R25", "R26"}
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
    index = [
        "# Recovered Myca character library", "",
        "239 original assets, deduplicated by SHA-256, with 290 filename aliases. "
        "46 of 49 reference IDs are recovered; R24–R26 remain missing or unmapped. "
        "The 15 detail crops match their recorded parent pixels. Inclusion is not whole-image approval.", "",
        "[All assets and filename aliases](Asset-Catalog.md) · "
        "[Separate membrane experiments](Experiments.md) · "
        "[Design history](Design-History.md) · [Coverage and validation](Recovery-Notes.md) · "
        "[Missing-resource records](Missing-Resources.json) · "
        "[Original recovery manifest](manifest.json)", "",
        "The [current character brief](../../docs/Myca%20Character%20Design%20Brief.md), "
        "[locomotion rules](../../docs/Myca%20Locomotion%20Reference.md), "
        "[reference index](../../docs/References/Reference%20Index.md), and "
        "[approval protocol](../../automation/README.md) remain authoritative. "
        "Recovered documents are unchanged historical snapshots. The manifest field "
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
            match = CROP.search(registry["full_entry"])
            index += [f"**Parent:** {match[1]}. **Bounds:** `({', '.join(match.group(2, 3, 4, 5))})` "
                      f"with exclusive right/bottom edges. **Size:** {match[6]} × {match[7]} pixels.", "",
                      "**Scope and inherited caveat:** " + registry["crop_scope"], ""]
        else:
            index += ["**Registry status:** " + registry["status"], "",
                      "**Use for:** " + registry.get("approved_scope", "No new approval recorded."), ""]
            if registry.get("known_defects"):
                index += ["**Do not inherit:** " + registry["known_defects"], ""]
            if registry.get("original"):
                index += ["**Registry original filename and dimensions:** " + registry["original"], ""]

    catalog = ["# Original assets and aliases", "",
               "[Reference IDs and feature caveats](Index.md) · [Membrane experiments](Experiments.md)", "",
               "Each link opens unchanged recovered bytes. Distinct hashes remain distinct, even when names or "
               "compositions resemble one another. An unavailable original filename is reported as unknown; "
               "the stored name is a Page label in those cases. A recovered filename containing “canonical” "
               "does not approve the complete design.", ""]
    for category in ("Supporting references and historical documents", "Pet and animation production",
                     "Living-membrane experiments", "Other experimental studies", "Cosplay inspiration"):
        selected = sorted((a for a in assets.values() if group(a) == category),
                          key=lambda a: (a["stored_filename"].casefold(), a["sha256"]))
        catalog += [f"## {category} · {len(selected)} assets", "",
                    "| Original bytes | Original filename | Known aliases | Classification | SHA-256 |",
                    "|---|---|---|---|---|"]
        for asset in selected:
            original = asset["original_filename"] if asset["original_filename"] is not None else "Unknown; Page label only"
            catalog.append(f"| {link(asset)} | {cell(original)} | {cell('; '.join(asset['filename_aliases']))} | "
                           f"{cell('; '.join(asset['classification']))} | `{asset['sha256']}` |")
        catalog.append("")

    experiments = ["# Living-membrane experiments", "",
                   "[Reference library](Index.md) · [All original assets](Asset-Catalog.md) · [Design history](Design-History.md)", "",
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
    checksums = {}
    for line in (LIBRARY / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", line)
        require(match is not None, "Invalid checksum entry")
        sha, name = match.groups()
        require(name not in checksums, f"Duplicate checksum path: {name}")
        require(digest(local_path(name)) == sha, f"Checksum failed: {name}")
        checksums[name] = sha
    require(len(checksums) == 242, "Recovery snapshot must retain 242 checksum entries")
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
        require(asset["original_bytes"] is True, f"Non-original object: {path.name}")
        require(asset["resource_path"] == f"resources/{sha[:16]}/{asset['stored_filename']}",
                f"Hash directory or filename differs: {path.name}")
        require(path.stat().st_size < 100 * 1024 * 1024, f"File requires storage outside regular Git: {path.name}")
        require(path.suffix.lower() != ".zip", "Nested archives must remain outside Git")
        require(asset["classification"] and asset["filename_aliases"], f"Missing metadata: {path.name}")
        require(asset["original_filename"] is None or asset["original_filename"] in asset["filename_aliases"],
                f"Original filename is not retained as an alias: {path.name}")
    require(len(assets) == 239 and sum(a["size_bytes"] for a in assets.values()) == 421078476,
            "Reviewed asset count or byte total differs")
    actual = {p.relative_to(LIBRARY).as_posix() for p in (LIBRARY / "resources").rglob("*") if p.is_file()}
    require(actual == {a["resource_path"] for a in assets.values()}, "Unexpected or missing asset files")
    refs = {r["reference_id"]: r for r in manifest["references"]}
    require(len(refs) == len(manifest["references"]) and set(refs) == EXPECTED_IDS,
            "Reference IDs must retain R01–R34 and C01–C15 exactly once")
    for rid, ref in refs.items():
        require(ref["design_registry"]["reference_id"] == rid, f"Registry identity differs: {rid}")
        require(ref["status"] == ("missing_or_unmapped" if rid in MISSING_IDS else "recovered"),
                f"Recovery state differs: {rid}")
        require(len(ref["asset_sha256"]) == (0 if rid in MISSING_IDS else 1), f"Asset mapping differs: {rid}")
        require(all(sha in assets for sha in ref["asset_sha256"]), f"Missing mapped bytes: {rid}")
    require(refs["R32"]["asset_sha256"] != refs["R34"]["asset_sha256"], "R32 and R34 must remain distinct")
    for rid in ("R32", "R33", "R34"):
        require("Experimental" in refs[rid]["design_registry"]["status"], f"Promoted membrane reference: {rid}")
        require("experimental membrane design" in assets[refs[rid]["asset_sha256"][0]]["classification"],
                f"Missing experimental classification: {rid}")
    for name, expected in rendered_indexes(manifest).items():
        require(local_path(name).read_text(encoding="utf-8") == expected, f"Navigation is stale: {name}")
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
            match = CROP.search(ref["design_registry"]["full_entry"])
            require(match is not None, f"Missing crop metadata: {rid}")
            parent = refs[match[1]]
            bounds = tuple(map(int, match.group(2, 3, 4, 5)))
            with Image.open(LIBRARY / assets[parent["asset_sha256"][0]]["resource_path"]) as original, \
                 Image.open(LIBRARY / assets[ref["asset_sha256"][0]]["resource_path"]) as detail:
                require(0 <= bounds[0] < bounds[2] <= original.width
                        and 0 <= bounds[1] < bounds[3] <= original.height, f"Invalid crop bounds: {rid}")
                require(detail.size == tuple(map(int, match.group(6, 7))), f"Crop size differs: {rid}")
                require(original.crop(bounds).convert("RGBA").tobytes() == detail.convert("RGBA").tobytes(),
                        f"Crop pixels differ from parent: {rid}")
    print("Verified 242 checksums; 239 distinct original assets; 49 reference records (46 recovered, 3 missing); 8 Page binary gaps.")
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
