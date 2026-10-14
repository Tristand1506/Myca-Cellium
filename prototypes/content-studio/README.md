# Content Studio interface prototype

An independently runnable, content-agnostic interface prototype, developed on the
`prototype/content-studio` branch of Myca-Cellium.

## Open it

Check out `prototype/content-studio`, then open
`prototypes/content-studio/index.html` in a current Chrome or Edge browser.
The complete folder must stay together: icons are bundled in `vendor/`.
No installation, package manager, build step, or internet connection is required.

For a loopback-only local server, run this from the repository root:

```sh
python -m http.server 8765 --bind 127.0.0.1 --directory prototypes/content-studio
```

Then open http://127.0.0.1:8765/ . In GitHub Desktop, Fetch origin, select the
prototype branch under Current branch, and choose Repository → Show in Explorer
(or Show in Finder) to locate the folder.

## Try the workflow

- **Timeline:** the root is at the bottom; current branch heads align horizontally.
  Pan, zoom, select a node, and inspect its summary in the side overlay.
- **Editor:** choose a branch and edit its current draft. Each field has pencil,
  up/down arrow, and trash controls; hover reveals their names. Manage fields
  provides a full name/order list. Field IDs remain stable when labels change.
- **Media:** add an Image or Image gallery field, import files through the picker,
  preview them, and arrange a gallery's image order.
- **Revisions:** record a revision explicitly. The dropdown and arrows let you
  view earlier versions without discarding drafts or changing other branches.
  Fork a direction, record detached work, connect it, combine recorded versions,
  or reinstate an earlier version by appending a new revision.
- **CMS / Preview:** arrange page sections and bind them to fields at the latest
  version or a pinned revision. Preview can show drafts; recorded output excludes
  drafts. Missing or incompatible fields/images block recorded export.

## Storage and limits

**This is a UI prototype. All edits and imported images stay in browser memory.
Reloading or closing the page resets them.** Recording a revision creates an
in-memory snapshot; it does not create a real Git commit.

There is no desktop shell, project-folder selection, persistent autosave,
filesystem watcher, or Git backend yet. The HTML/CSS view displays generated HTML
and lets you edit CSS. Recorded export displays HTML for review; it does not write
a project file. External-file handling is simulated.

The Git branch stores the application's source, bundled icons, design notes, and
tests. It does not contain anything imported into a running prototype session.

## Separation from Myca

This folder uses neutral sample content and has no connection to the existing
Review Desk backend, original artwork, collections, regions, archive decisions,
canon registers, or authenticated canon approval workflow. Generic branch/head
selection grants no Myca canon approval. The Pages builder does not include this
folder. Deployment and existing workflows are unchanged.

See [DESIGN.md](DESIGN.md) for the agreed system behavior and remaining backend
work, and [THIRD_PARTY.md](THIRD_PARTY.md) for offline icon attribution.

## Tests

From the repository root:

```sh
python -m unittest discover -s prototypes/content-studio/tests -v
```

Python 3.10+ and Chrome, Chromium, or Edge are required for browser checks.
The test driver uses only the Python standard library and loopback DevTools.
Set `CONTENT_STUDIO_BROWSER` to a browser executable if automatic discovery
does not find one. Browser tests report a skip when no browser is installed;
set `CONTENT_STUDIO_REQUIRE_BROWSER=1` to make that a failure, as in CI.

Tests create synthetic PNGs in a temporary folder. No character artwork is used.
