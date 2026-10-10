# Myca Cellium · Character Design Repository

A version-controlled, **feature-scoped** character reference with a read-only GitHub Pages publication workflow. Written approved design rules are authoritative; generated images are not blanket canon.

## Current import

The existing source Markdown documents and the legacy embedded-preview HTML are preserved in `docs/` without rewriting their content. Some resource files and original reference image binaries were not present in the available attachment set; see `data/resource-status.json`. Missing files are **not** represented as imported.

## How to use

- `docs/Myca Character Design Brief.md`: primary appearance and membrane candidates.
- `docs/Myca Locomotion Reference.md`: movement and contact only.
- `docs/References/Reference Index.md`: feature-scoped evidence and caveats.
- `data/canon-register.json`: structured index pointing to written authority, **not** a replacement for it.
- `PROJECT_INSTRUCTIONS.md`: condensed project guidance under 8,000 characters.
- `python scripts/validate.py`: deterministic integrity checks.
- `python scripts/build_site.py`: build a static searchable documentation overview in `_site/`.

## Canon change protocol

1. Create an `experiment/*` or `refinement/*` branch.
2. Edit the relevant authoritative written page first. Preserve old source and identifiers.
3. Mark proposals experimental/provisional unless the creator explicitly approved the specific feature.
4. Run validation and inspect the rendered diff/site.
5. Have the creator approve the exact scope before merging a change to canon. An automated checker may flag errors; **it cannot approve design changes**.

## GitHub Pages deployment

The `.github/workflows/pages.yml` workflow builds and deploys the site only when manually run from the Actions tab. Commits to `main` validate the repository but do not publish the site. In GitHub repository **Settings → Pages → Build and deployment**, select **GitHub Actions** when you are ready to enable hosting, then manually run **Publish Myca library**. Pages hosting is public to website visitors: do not put private or sensitive resources in the published source. This repository should be configured deliberately as public or private depending on desired visibility and plan support.

## Important

`docs/Myca Resource Guide.html` is the preserved browser edition with embedded previews and is large (~8.6 MB). The generated index links to it. Individual links to missing original image files may not work until the full original resource directory is imported. This is not a completed visual-asset migration.
