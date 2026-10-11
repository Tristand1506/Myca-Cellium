# Myca Review Desk · prototype

A local browser workspace for organizing the recovered image library. It does not connect to GitHub, commit, push, merge or deploy anything automatically.

## Start

From this repository's root, with Python **3.11 or newer**:

```sh
python scripts/review_desk.py
```

Open **http://127.0.0.1:8765**. Use `--port 8766` if that port is occupied. Stop with Ctrl+C. The editor needs no third-party Python packages. Startup verifies the public recovery snapshot and artwork; the large collection can take a few seconds to check.

On Windows, use a checkout inside **WSL's Linux filesystem** if Git reports invalid filenames. The existing preserved library includes names containing `:`, which native Windows filesystems cannot represent. This prototype does not rename originals to work around that limitation.

## Review workflow

1. Search by filename, R/C reference ID, recorded scope or caveat. Browse active artwork, unassigned items, existing crops, saved views or the archive.
2. Create or rename feature collections. Select several cards and add them to a collection. One item may appear in several collections; adding membership never moves the file.
3. Open an image to inspect its recorded feature scopes and defects. Write a private review note; it autosaves locally. It is not a canon approval.
4. Choose **Draw detail region**. Drag a rectangle, or enter its percentage bounds for keyboard-accessible precision. Give it a public title and save. A detail view opens focused on that region; **Focus detail / show parent** toggles the context. The parent image is not cropped, rewritten or duplicated.
5. Select **exactly two** images or saved views and choose Compare. Zoom, review the caveats, and archive only the versions you choose. No similarity algorithm automatically merges or deletes distinct images.
6. Archive an original immediately, or select several originals for a batch move. Saved views are not separate files; archiving a view's parent hides its linked regions from active public browsing. Collections retain membership so Restore brings the organization back.
7. Undo reverses the last edit, including file moves. The last 100 changes are recorded across restarts. If a file was changed externally or a destination already exists, the operation stops without overwriting it.

## Where changes go

| State | Location | Visibility |
|---|---|---|
| Collections, region coordinates and archive membership | `data/review-desk.json` | Tracked, public-ready |
| Archived original images | `resources/character-library/Archive/ReviewDesk/resources/<hash>/<filename>` | Tracked, unchanged bytes |
| Live resource navigation | `Index.md`, `Asset-Catalog.md`, `Experiments.md` in the library | Regenerated for moved paths |
| Private notes, undo history and pending-operation recovery | `.review-desk/` | Git-ignored; never copied into the website |

The original recovery `manifest.json` and `SHA256SUMS` remain byte-identical. Their paths are the original logical locators; the validator uses the organization sidecar to find archived bytes. Use the repository's Python validator rather than a raw `sha256sum -c` after archiving.

The website builder preserves the old public original URLs and illustrated-guide compatibility paths. Archived artwork also has physical-path download links for the regenerated catalog. **Archive is not privacy:** archived images remain publicly accessible and appear on the Archive page. Collections exclude archived parents from active browsing. Experimental classifications and scoped caveats remain visible, including on virtual detail views. New views do not receive R/C IDs or new feature approvals.

Private notes remain only in this checkout; back up `.review-desk/` privately if you need them on another machine. Never force-add that directory to Git. The server refuses to start if it detects tracked private state. Do not expose the editor through a reverse proxy or bind it to a network interface.

## Publish curated organization

Review the Git diff, especially archive moves and generated navigation. Commit and push the public changes through your usual branch/PR workflow. Public labels and region titles should contain only material you intend to publish.

The existing manual GitHub Pages build includes **Collections**, **Archive**, and a strict-schema `review-collections.json`. It excludes private notes and all local editor files. The illustrated guide and original artwork bytes are preserved. Nothing deploys just because you save a review.

For a local website build, install the existing builder dependency in your preferred environment:

```sh
python -m pip install 'mistune>=3,<4'
python scripts/resource_library.py validate
python scripts/build_site.py
python scripts/validate_site.py
python -m unittest discover -s tests -v
```

Optional full-corpus regression (temporary copies require roughly 1 GB free; Pillow is needed for decoding checks):

```sh
MYCA_FULL_STORE_TEST=1 python -m unittest discover -s tests -p test_review_desk_integration.py -v
```

## Prototype limits

No document/video organization, uploads, similarity suggestions, freeform painting, new bitmap crops, Git controls or canon-approval controls. The image editor is loopback-only with per-session write tokens, Host/Origin checks, a single-process repo lock and a crash-recovery journal. It is not a multi-user service. Do not switch branches or edit organization files while it is running; a stale tab or external metadata edit is rejected.

Automated tests cover data operations, byte identity, recovery, private-state exclusion, public links and UI logic. Browser layout and touch interaction still need a hands-on acceptance pass.
