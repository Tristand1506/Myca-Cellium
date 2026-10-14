# Agreed system design

## Purpose and boundaries

A desktop-oriented, content-agnostic design and iteration system that opens
ordinary project folders. Git will supply recorded history and branch ancestry;
the interface will supply the visual workflow. Content remains ordinary Markdown,
text, and native media files, with readable metadata for stable field IDs.

The checked-in interface demonstrates interactions only. Its in-memory model is
not a Git implementation or a persistence schema. Production storage must use
validated metadata and atomic writes, retain originals, and provide Undo.

## Timeline

A timeline always retains at least one editable mainline content branch. Its
revisions and related branches form a directed acyclic graph. Adjacency supports
moving through a branch's revisions; multiple parents represent explicit combined
work. A doubly linked list alone cannot describe branching and convergence.

Each recorded revision has its own branch-local version stamp. Recording one
branch leaves other branch stamps and selections unchanged. Drafts autosave
separately; only an explicit Record action adds a revision node.

Forking copies the selected node's fields and content. Detached work can record
its own history before connection. Attaching it as a revision defaults to its
complete content; combining is a separate, explicit operation. Reinstating an
older revision appends a copy at the branch head and retains every forward node.
A dirty draft must be retained or explicitly recorded before reinstatement.

The visual tree grows upward from the bottom root, with current branch heads on
a common horizontal row and detached work in a separate area. Circular head nodes
keep branch names and subtitles visible; older nodes reveal details on
hover/focus/selection. The canvas pans and zooms. A side summary overlays the
canvas without displacing it.

## Editor

Branches have independently selected revisions. Browsing an older version keeps
the current draft and all unrelated branch selections intact. Historical versions
are read-only; Edit current draft provides an explicit return to editable work.

Fields have stable IDs, display names, types, content, and order. Renaming changes
the display name, not the ID or CMS binding. Reordering changes presentation order
without changing field content. Text and Markdown fields remain native text;
single-image and gallery fields refer to ordinary media assets. Gallery selections
retain ordered asset identities, including when filenames collide.

Templates define initial fields, IDs, and values for new content. Template changes
apply only to new content. External edits should update drafts automatically;
only conflicts need user resolution. The current interface simulates this flow.

## CMS and renderer

Pages, layouts, and templates support a visual editor with an optional HTML/CSS
view. Static content belongs to the page/layout. Dynamic content binds by field ID
to a selected branch or node, following its latest recorded revision or pinning an
exact revision. Branch histories are independent.

Preview may show autosaved drafts and must label that state. Export resolves
recorded revisions only. Missing fields, unavailable images, and media type
mismatches produce clear warnings and block export.

The renderer generates ordinary HTML. The current prototype previews generated
HTML and displays recorded output for inspection; production filesystem export
remains to be implemented.

## Planned production work

- Desktop shell and ordinary folder opening.
- A precise Git mapping for branch identities, immutable recorded revisions,
  parent relationships, detached work, and independent version selection.
- Native content files and validated, readable metadata with atomic saves.
- Draft persistence, conflict-aware filesystem watching, Undo, and schema upgrades.
- Cycle and invalid-reference validation at the storage boundary.
- Richer CMS layouts/templates and filesystem HTML export.
- Workflow labels for experimental directions and legacy/obsolete revisions.
- Any future Myca integration must retain original artwork bytes and R/C IDs,
  private review records, existing organization, and authenticated canon approval.

These are requirements for future work, not claims about the current prototype.
