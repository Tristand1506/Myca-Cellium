# Myca Review Desk · prototype

A local browser workspace for organizing the recovered image library. It does not connect to GitHub, commit, push, merge or deploy anything automatically.

## Start

From this repository's root, with Python **3.11 or newer**:

```sh
python scripts/review_desk.py
```

Open **http://127.0.0.1:8765**. Use `--port 8766` if that port is occupied. Stop with Ctrl+C. The editor needs no third-party Python packages. Startup verifies the public recovery snapshot and artwork; the large collection can take a few seconds to check.

Windows checkouts are supported by the storage-path fix merged in PR #6. Thirty colon-containing storage labels use a portable separator; previous source labels remain alias metadata, and artwork bytes and hashes are unchanged. The Review Desk uses the current manifest paths for image lookup, archive moves and Undo. No WSL filename workaround is required.

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

## Feature-reference navigation

The manual Pages build also generates **By feature** and `feature-references.json`.
It uses the saved public sidecar, not private notes or Undo history. Explicit
`data/collection-features.json` mappings associate stable collection IDs with review
topics. New or unmapped collections stay organizational until a mapping is added;
renaming does not infer a new topic, and deleting a collection creates no assignments.

Every assigned item retains its recorded R/C identities, exact scope, status and
classification. Registered crops also show their parent reference's limits; saved
regions keep their original coordinates and receive no R/C ID. Archived memberships
remain in the derived index and history view, with links to unchanged originals.

**Selecting a reference for a topic does not approve that feature.** For example,
placing a lichen-only crop into Face and eyes does not approve its facial anatomy.
All existing written authority and specific creator approvals still control use.

Saving in the Review Desk writes `data/review-desk.json` locally. Commit and push it
through a PR before building Pages from the remote branch. A generated feature index
is derived output, not a second editable source of memberships.

## Separate and compare membrane directions

Open **Compare membranes** in the built site. Filter by growth architecture, select
two to four whole studies or linked regions, then choose **Compare selected**.
Selections survive direction changes. Equal-height frames preserve the source
proportions; they do not normalize character scale, pose or lighting. On small
screens, the comparison scrolls horizontally within its own frame. Without
JavaScript, linked-region cards show the full, undistorted original with the region
coordinates below; whole-study cards and source limitations remain available.

The working **Membrane · ...** collections separate petal, single-sheet, vascular,
gill-frill, veil-streamer, spore-lace, shelf-fungus, lily/bud and mixed-sheet studies.
The seven documented candidates remain experimental. Lily/bud is an organizational
working direction, not a new canon candidate. Vascular currently has no clearly
assigned representative; ambiguous studies stay Unsorted.

Use the existing Review Desk collection actions to add or remove members, and draw
additional linked regions without changing artwork. One source may belong to
multiple directions. The original broad Membrane experiments collection and all
other existing memberships are preserved. Existing R/C identifiers remain intact; these presentation regions use view IDs
and receive no R/C identifiers.

`data/membrane-layout.json` maps stable collection IDs to direction headings.
Adding another direction requires a matching collection and a layout entry.
Public memberships and coordinates remain in `data/review-desk.json`.
Browser comparison selections are temporary and do not write or publish anything.
Commit saved organization through a PR; publication still uses the manual workflow.

### Browser regression check

After building the site, use Playwright with Chromium installed to check all seven
linked regions on desktop and mobile, with JavaScript enabled and disabled:

```bash
node tests/test_membrane_browser.js
```

The check uses the installed `playwright` module. `MYCA_PLAYWRIGHT_PATH` can point to
an existing module installation instead. This browser check runs separately from
the Python suite.

## Prototype limits

### Windows line endings and checksum startup errors

The repository's `.gitattributes` disables Git text conversion for the recovered
library and preserved source documents. This retains exact original bytes,
including historical files that intentionally use CRLF.

If an older checkout reports `Reviewed snapshot changed: SHA256SUMS`, pull this
branch's latest changes, then run:

```sh
python scripts/repair_checkout_bytes.py --apply
python scripts/review_desk.py
```

The repair restores a file only when its bytes exactly equal the committed
original with LF converted to CRLF. Other edits are reported and left alone;
missing or moved files are not recreated. Staged changes in protected files
must first be committed or unstaged. Omit `--apply` for a read-only preview.
Checksum checks and pinned metadata hashes remain unchanged.

No document/video organization, uploads, similarity suggestions, new bitmap crops, Git controls or canon-approval controls. The image editor is loopback-only with per-session write tokens, Host/Origin checks, a single-process repo lock and a crash-recovery journal. It is not a multi-user service. Do not switch branches or edit organization files while it is running; a stale tab or external metadata edit is rejected.

Automated tests cover data operations, byte identity, recovery, private-state exclusion, public links and UI logic. Browser regressions cover desktop/mobile layout; physical touch interaction still needs a hands-on acceptance pass.

## v0.3 · Private visual annotations

Choose a mark tool in an image review, then drag a rectangle, ellipse, arrow or
freehand stroke; click for a pin. Add a comment, feature, severity and workflow
status, then Save mark. Select a mark in the list or on the image to move it.
Drag its endpoint handles to edit geometry, or enter normalized points directly.
Freehand endpoint handles edit the first/last points; the JSON field can edit
every point. Save commits the whole edit; Cancel edit discards the draft.

All coordinates refer to the full unchanged original, including marks attached
to saved regions. Region focus clips the vector layer along with its parent
image. Marks are local records in ignored `.review-desk/local.json`, never
painted into source pixels and never copied into Pages. Legacy notes and Undo
records remain readable. Each saved edit participates in atomic transactions,
crash recovery, stale-tab checks and persistent Undo. Private-only saves do not
rewrite public collection metadata. Deleting a detail view removes its attached
private marks; Undo restores both.

Run `python -m unittest discover -s tests -v`. The suite exercises a real
headless Chrome/Edge browser when installed, using a temporary artwork fixture.
`MYCA_BROWSER` can select its executable. Browser checks skip explicitly when no
supported browser exists. The existing validation and authenticated canon
approval workflows remain unchanged.

## v0.3 · Advanced private comparisons

Select two to four originals or saved regions and Compare. Side-by-side panes
support wheel/buttons/keyboard zoom and pointer/arrow-key pan. Sync shares
navigation changes across panes; each pane retains its own alignment. Manual
alignment provides X/Y offsets (fractions of pane size), scale and rotation.
These transforms affect display only. Fit resets a pane; Reset all transforms
resets the entire comparison. Independent crop fitting preserves image aspect.

With exactly two items, choose adjustable-opacity Overlay or Before / after.
The split range reveals the second image over the first. Dragging the visible
comparison navigates the first pane (and other panes when Sync is enabled).
Use the second pane's buttons/alignment fields to adjust it independently.

Give the session a private name and Save session. Saved comparisons can be
restored or deleted from the header button and session selector. Saving a loaded
session updates it; a new selection creates another. Changes remain temporary
until saved. Delete and save participate in persistent Undo. Deleting a saved
region removes sessions that depend on it; Undo restores both. Original scopes,
known defects and experimental warnings remain visible in every mode.

## v0.3 · Iteration history

Open Iteration history, or Record iteration from an image review. A source node
has no parents. A revision or alternative branch has one or more existing
parents. Each record links an unchanged registered image and can retain targeted
features, requested corrections, a source prompt when known, and review outcome.
The server validates all asset/parent references and uses a nonrecursive
topological check to prevent cycles, including cycles introduced by edits.

The graph shows directed parent-to-child links, with a text list below for
keyboard access. Select a node to inspect its image scopes and edit its record.
Record iteration starts a fresh record and discards an unsaved form. Saving and
deleting participate in persistent Undo. A parent cannot be deleted while a
child still references it: edit the child links first. Archiving an original
does not break its history; links use stable SHA-256 identities. Records and
prompts stay private, and review outcomes do not change canonical status.

## v0.3 · Review queue and candidate nomination

Review queue has lanes for unreviewed artwork, unresolved annotations,
refinement candidates, nominated candidates and completed reviews. Filter by
feature, severity, workflow status and experimental family. Archived artwork is
hidden until Include archived is enabled; its archive decision stays intact.
Family filters inherit existing membrane collection memberships and can also
use a private review label. These labels classify work, not canonical design.

Choose Review / nominate to set a workflow status and optional candidate
nomination, with a private reason. Inspect image / annotations opens its existing
reviewer so marks can be corrected or resolved. Completing a workflow review
does not resolve outstanding marks automatically, so an image may appear in the
completed and unresolved lanes. Iteration outcomes marked needs-refinement also
appear in the refinement lane. Clear workflow record restores default unreviewed
status; save, clear and nomination changes support persistent Undo.

All new review data lives in ignored `.review-desk/`. No new field is accepted
by the public organization schema. The Pages builder, artwork, R01–R34/C01–C15
registry, canon ledgers and authenticated creator-approval workflow are unchanged.
There is no database or framework migration, no automatic canon promotion,
commit, merge or deployment. This is a single-user local workspace; back up the
ignored private directory separately if its review history matters.

### v0.3 validation and limits

The Python suite includes real Chrome/Edge browser interactions using only the
standard library and the browser's local DevTools interface. No browser testing
dependency, workflow rewrite or server framework is required. A headless runner
does not replace an actual Windows/touch acceptance pass. Full-corpus publication
QA remains available through `MYCA_FULL_STORE_TEST=1` after installing the
existing site dependencies (`mistune` and `Pillow`). Private comparison drafts
are temporary until saved; alignment does not resample image pixels.
