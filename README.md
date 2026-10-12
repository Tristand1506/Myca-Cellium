# Myca Cellium · Character Design Repository

A version-controlled, **feature-scoped** character reference with a read-only GitHub Pages publication workflow. Written approved design rules are authoritative; generated images are not blanket canon.

## Recovered character library

The [recovered resource index](resources/character-library/Index.md) opens the original character images, reference sheets, detail crops, animation studies, and design-document snapshots. It contains 234 public assets: 232 unchanged originals and two clearly labeled sanitized metadata derivatives, with 315 current filename aliases. The unchanged source documents for those derivatives remain in the owner archive. Of the 49 R01–R34 and C01–C15 identifiers, 46 are recovered; R24–R26 remain missing or unmapped, and eight Page-linked binaries remain unavailable.

[Browse all assets and aliases](resources/character-library/Asset-Catalog.md), [review the separate membrane experiments](resources/character-library/Experiments.md), or read the [sanitation report](resources/character-library/Sanitation-Report.md). SHA-256 fingerprints preserve byte identity. Supporting documents remain historical snapshots; the existing canon documents and feature-specific approvals remain authoritative.

Run `python scripts/resource_library.py validate` to check the complete recovery snapshot and navigation. Add `--images` when Pillow is available to decode all images and verify the 15 crop-to-parent pixel comparisons.

## Original document import

The existing source Markdown documents and the legacy embedded-preview HTML are preserved in `docs/` without rewriting their content. The initial attachment gaps are historical; the recovered artwork and document snapshots are now available. Current gaps are R24–R26 and eight unavailable binaries; see `data/resource-status.json`. Missing files are **not** represented as imported.

The preserved documents describe a fuller resource bundle. The original import lacked the original images and crops, acting guide, review checklist, decision log, and archived S01–S03 source documents. Those recovered files now have links in the resource index above. Prior-layout links in downloadable historical snapshots remain unchanged. The rendered website resolves verified references; ambiguous historical document versions link to the catalog. The illustrated guide and its 49 embedded previews retain their exact source bytes, with verified compatibility paths for its original-file links.

## How to use

- `docs/Myca Character Design Brief.md`: primary appearance and membrane candidates.
- `docs/Myca Locomotion Reference.md`: movement and contact only.
- `docs/References/Reference Index.md`: feature-scoped evidence and caveats.
- `data/canon-register.json`: structured index pointing to written authority, **not** a replacement for it.
- `PROJECT_INSTRUCTIONS.md`: condensed project guidance under 8,000 characters.
- `python scripts/validate.py`: deterministic integrity checks.
- `python scripts/build_site.py`: build the static reference gallery, separate experiments, documentation and verified public assets in `_site/`.

## Canon change protocol

1. Create an `experiment/*` or `refinement/*` branch.
2. Edit the relevant authoritative written page first. Preserve old source and identifiers.
3. Mark proposals experimental/provisional unless the creator explicitly approved the specific feature.
4. Run validation and inspect the rendered diff/site.
5. Have the creator approve the exact scope before merging a change to canon. An automated checker may flag errors; **it cannot approve design changes**.

## GitHub Pages deployment

The `.github/workflows/pages.yml` workflow builds and deploys the site only when manually run from the Actions tab. Commits to `main` validate the repository but do not publish the site. In GitHub repository **Settings → Pages → Build and deployment**, select **GitHub Actions** when you are ready to enable hosting, then manually run **Publish Myca library**. Pages hosting is public to website visitors: do not put private or sensitive resources in the published source. This repository should be configured deliberately as public or private depending on desired visibility and plan support.

## Important

`docs/Myca Resource Guide.html` is the preserved browser edition with embedded previews and is large (~8.6 MB). The generated documentation site links to it. Use the recovered resource index for original image files; its hash-based paths preserve distinct variants and filename collisions. Recovery still has the explicit gaps listed above.

## Website validation

The Pages builder validates the sanitised manifest and checksum pins before writing output. It copies only the 234 listed assets and named public metadata/navigation files; private archives and unlisted recovery files are excluded. The reference gallery shows exact registry scopes and caveats. Membrane experiments and other experimental studies are on a separate page; archive inclusion does not grant canon approval. Originals are lazy-loaded and remain byte-identical.

```sh
python scripts/resource_library.py validate --images
python scripts/build_site.py
python scripts/validate_site.py
python -m unittest discover -s tests -v
```

The existing Pages workflow remains manual. Review and merge the website PR, then run **Publish Myca library** from `main` to deploy. This change does not automatically merge or deploy.

## Windows checkout compatibility

Thirty recovered storage filenames containing colons use a portable ` -` separator. Their previous source labels remain filename aliases; original artwork bytes, SHA-256 hashes, reference IDs and canon scopes are unchanged. Alias labels are descriptive metadata, not additional filesystem paths. Run `python scripts/windows_paths.py` to check the working index for reserved characters, device names, trailing dots/spaces and case-insensitive collisions.
