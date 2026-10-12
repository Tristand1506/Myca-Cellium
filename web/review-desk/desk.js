"use strict";
// No external services, generated image bytes, or notes in public metadata.
const $ = id => document.getElementById(id);
let state, token, view = "active", selection = new Set(), visible = [], current = null;
let queue = Promise.resolve(), noteTimer, pendingNote = null, drawing = false, dragStart = null, rect = null;
let textResolve, toastTimer;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function button(text, action, className = "") {
  const node = element("button", className, text); node.type = "button";
  node.addEventListener("click", () => run(action)); return node;
}
function run(action) { Promise.resolve().then(action).catch(error => toast(error.message)); }
function toast(message) { $("toast").textContent = message; $("toast").hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => { $("toast").hidden = true; }, 6500); }
function mutate(action, data = {}) {
  const operation = queue.catch(() => {}).then(async () => {
    const response = await fetch("/api/change", {method: "POST", headers: {"Content-Type": "application/json", "X-Review-Token": token}, body: JSON.stringify({action, ...data, version: state.version})});
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || "Could not save change");
    state = value; render(); return value;
  });
  queue = operation; return operation;
}
function items() {
  const images = state.assets.map(asset => ({id: asset.sha256, asset, title: asset.references[0]?.design_registry.title || asset.stored_filename}));
  const details = state.public.details.map(detail => ({id: detail.id, asset: state.assets.find(a => a.sha256 === detail.asset_sha256), title: detail.title, detail}));
  return [...images, ...details];
}
function findItem(id) { return items().find(item => item.id === id); }
function isExperimental(asset) { return asset.classification.some(label => label.includes("experiment")); }
function collection() { return state.public.collections.find(c => c.id === view); }
function size(bytes) { return `${(bytes / 1024 / 1024).toFixed(1)} MB`; }
function identity(item) { return item.detail ? "SAVED DETAIL · PARENT " + (item.asset.references.map(r => r.reference_id).join(" / ") || item.asset.sha256.slice(0, 8)) : item.asset.references.map(r => r.reference_id).join(" / ") || "UNMAPPED · " + item.asset.sha256.slice(0, 8); }

function regionImage(item) {
  if (!item.detail) {
    const image = element("img"); image.src = item.asset.url; image.alt = item.title; image.loading = "lazy"; image.decoding = "async"; return image;
  }
  const frame = element("div", "detail-frame"), image = element("img");
  const [l, t, r, b] = item.detail.rect;
  image.alt = item.title; image.loading = "lazy"; image.decoding = "async";
  image.style.width = `${100 / (r - l)}%`; image.style.height = `${100 / (b - t)}%`;
  image.style.left = `${-100 * l / (r - l)}%`; image.style.top = `${-100 * t / (b - t)}%`;
  const fit = () => {
    const ratio = image.naturalWidth * (r - l) / (image.naturalHeight * (b - t));
    if (!Number.isFinite(ratio) || !frame.parentElement) return;
    const width = Math.min(frame.parentElement.clientWidth, frame.parentElement.clientHeight * ratio);
    frame.style.width = `${width}px`; frame.style.height = `${width / ratio}px`; frame.style.aspectRatio = `${ratio}`;
  };
  image.addEventListener("load", fit);
  if (typeof ResizeObserver !== "undefined") new ResizeObserver(fit).observe(frame);
  image.src = item.asset.url; frame.append(image); return frame;
}

function card(item) {
  const article = element("article", "image-card" + (selection.has(item.id) ? " selected" : ""));
  const label = element("label", "select-check"), check = element("input"); check.type = "checkbox"; check.checked = selection.has(item.id); check.setAttribute("aria-label", "Select " + item.title);
  check.addEventListener("change", () => { check.checked ? selection.add(item.id) : selection.delete(item.id); article.classList.toggle("selected", check.checked); selectionBar(); }); label.append(check);
  const open = button("", () => openViewer(item.id), "image-open"); open.setAttribute("aria-label", "Review " + item.title); open.append(regionImage(item));
  const body = element("div", "card-body"); body.append(element("p", "card-id", identity(item)), element("h3", "card-title", item.title));
  const badges = element("div", "badges");
  if (item.detail) badges.append(element("span", "badge detail", "Detail view"));
  if (isExperimental(item.asset)) badges.append(element("span", "badge experiment", "Experimental"));
  if (item.asset.archived) badges.append(element("span", "badge archived", "Archived"));
  const count = state.public.collections.filter(c => (item.detail ? c.details : c.assets).includes(item.id)).length;
  if (count) badges.append(element("span", "badge", `${count} collection${count === 1 ? "" : "s"}`));
  body.append(badges, element("p", "muted", size(item.asset.size_bytes) + (item.detail ? " · linked region" : " · unchanged original")));
  article.append(label, open, body); return article;
}

function render() {
  const all = items(), activeCollection = collection();
  for (const id of selection) if (!findItem(id)) selection.delete(id);
  $("library-summary").textContent = `${state.assets.length} preserved images · ${state.assets.filter(a => a.references.length).length} mapped files · ${state.public.details.length} saved detail views`;
  $("undo").disabled = !state.undo_count; $("undo-count").textContent = state.undo_count ? `(${state.undo_count})` : "";
  const libraryNav = $("library-nav"); libraryNav.replaceChildren();
  for (const [id, name, count] of [["active", "All active images", state.assets.filter(a => !a.archived).length], ["details", "Saved detail views", state.public.details.length], ["unassigned", "Not in a collection", state.assets.filter(a => !a.archived && !state.public.collections.some(c => c.assets.includes(a.sha256))).length], ["archive", "Archive", state.public.archived.length]]) {
    const node = button(name, () => { view = id; selection.clear(); render(); }, "nav-item" + (view === id ? " active" : "")); node.append(element("small", "", count)); libraryNav.append(node);
  }
  $("collections").replaceChildren();
  for (const c of state.public.collections) {
    const node = button(c.name, () => { view = c.id; selection.clear(); render(); }, "nav-item" + (view === c.id ? " active" : "")); node.append(element("small", "", c.assets.length + c.details.length)); $("collections").append(node);
  }
  const terms = $("search").value.toLowerCase().trim().split(/\s+/).filter(Boolean), kind = $("kind").value;
  visible = all.filter(item => {
    if (activeCollection) { if (!(item.detail ? activeCollection.details : activeCollection.assets).includes(item.id)) return false; }
    else if (view === "archive") { if (!item.asset.archived) return false; }
    else if (view === "details") { if (!item.detail || item.asset.archived) return false; }
    else if (item.asset.archived) return false;
    if (view === "unassigned" && state.public.collections.some(c => (item.detail ? c.details : c.assets).includes(item.id))) return false;
    if (kind === "references" && (!item.asset.references.length || item.detail)) return false;
    if (kind === "crops" && (item.detail || !item.asset.references.some(r => r.reference_id.startsWith("C")))) return false;
    if (kind === "details" && !item.detail) return false;
    if (kind === "unmapped" && (item.asset.references.length || item.detail)) return false;
    if (kind === "experiments" && !isExperimental(item.asset)) return false;
    const text = [item.title, identity(item), ...item.asset.filename_aliases, ...item.asset.classification, ...item.asset.references.map(r => JSON.stringify(r.design_registry))].join(" ").toLowerCase();
    return terms.every(term => text.includes(term));
  });
  const sort = $("sort").value;
  visible.sort((a, b) => sort === "size" ? b.asset.size_bytes - a.asset.size_bytes : (sort === "reference" ? identity(a).localeCompare(identity(b)) : a.title.localeCompare(b.title)));
  $("view-title").textContent = activeCollection?.name || ({active: "All active images", details: "Saved detail views", unassigned: "Not in a collection", archive: "Archive"}[view]);
  $("result-count").textContent = `${visible.length} items`;
  $("rename-collection").hidden = $("delete-collection").hidden = !activeCollection;
  $("grid").replaceChildren(...visible.map(card)); $("empty").hidden = visible.length !== 0;
  const chosen = $("assign-collection").value; $("assign-collection").replaceChildren(...state.public.collections.map(c => { const option = element("option", "", c.name); option.value = c.id; return option; }));
  if (state.public.collections.some(c => c.id === chosen)) $("assign-collection").value = chosen;
  if (current) current = findItem(current.id) || null;
  selectionBar();
  if (typeof refreshAnnotations === "function") refreshAnnotations();
  if (typeof renderIterations === "function" && $("history-dialog").open) renderIterations();
  if (typeof renderReviewQueue === "function" && $("queue-dialog").open) renderReviewQueue();
}
function selectionBar() {
  $("selection-bar").hidden = selection.size === 0;
  $("selected-count").textContent = `${selection.size} selected`;
  $("compare").disabled = selection.size < 2 || selection.size > 4; $("compare").title = "Select two to four images or detail views";
  $("add-selection").disabled = !state.public.collections.length;
  $("remove-selection").hidden = !collection();
  $("archive-selection").hidden = view === "archive";
  $("restore-selection").hidden = view !== "archive";
  $("archive-selection").disabled = [...selection].every(id => findItem(id)?.detail);
  $("restore-selection").disabled = [...selection].every(id => findItem(id)?.detail);
}
function selectedItems() { const list = [...selection].map(findItem).filter(Boolean); return {assets: list.filter(i => !i.detail).map(i => i.id), details: list.filter(i => i.detail).map(i => i.id)}; }
function requestText(title, value = "") {
  $("text-title").textContent = title; $("text-value").value = value; $("text-dialog").showModal(); $("text-value").focus();
  return new Promise(resolve => { textResolve = resolve; });
}
function textDone(value) { $("text-dialog").close(); textResolve?.(value); textResolve = null; }
function scopeContent(item) {
  const node = element("div");
  if (isExperimental(item.asset)) node.append(element("span", "badge experiment", "Experimental — not baseline canon"));
  if (item.detail) node.append(element("p", "muted", "Saved region only. It inherits every limitation of the parent artwork; it is not a corrected image or new R/C reference."));
  const references = [...item.asset.references];
  for (const ref of item.asset.references) if (ref.reference_id.startsWith("C") && ref.crop) {
    const parent = state.assets.flatMap(a => a.references).find(r => r.reference_id === ref.crop.parent_reference_id);
    if (parent && !references.includes(parent)) references.push(parent);
  }
  if (!references.length) node.append(element("h3", "", "No recorded feature approval"), element("p", "", "Unmapped supporting artwork. Filenames, collections and review notes do not establish canon."));
  for (const ref of references) {
    const r = ref.design_registry;
    node.append(element("h3", "", `${ref.reference_id} · Use scope`), element("p", "", r.crop_scope || r.approved_scope || "No new approval recorded."));
    if (r.known_defects) { const caveat = element("div", "caveat"); caveat.append(element("h3", "", "Do not inherit"), element("p", "", r.known_defects)); node.append(caveat); }
  }
  return node;
}
function memberships(item) {
  $("memberships").replaceChildren(element("h3", "", "Feature collections"));
  for (const c of state.public.collections) {
    const label = element("label", "membership"), check = element("input"); check.type = "checkbox"; check.checked = (item.detail ? c.details : c.assets).includes(item.id);
    check.addEventListener("change", () => run(() => mutate("collection_assign", {id: c.id, assets: item.detail ? [] : [item.id], details: item.detail ? [item.id] : [], remove: !check.checked})));
    label.append(check, document.createTextNode(c.name)); $("memberships").append(label);
  }
}
async function openViewer(id) {
  if (typeof requireSavedMark === "function") requireSavedMark();
  await flushNote(); current = findItem(id); if (!current) return;
  if (typeof resetAnnotations === "function") resetAnnotations();
  drawing = false; rect = current.detail ? [...current.detail.rect] : null;
  $("viewer-id").textContent = identity(current); $("viewer-title").textContent = current.title;
  $("scope").replaceChildren(scopeContent(current)); memberships(current);
  $("private-note").value = state.notes[current.id] || ""; $("note-status").textContent = "Notes autosave locally.";
  $("region-form").hidden = $("region-help").hidden = true;
  $("image-stage").classList.remove("drawing"); $("zoom").value = "fit";
  $("full-image").alt = current.title; $("full-image").src = current.asset.url;
  $("full-image").onload = () => {
    setZoom(); showRect();
    if (current?.detail) focusDetail(true);
    if (typeof refreshAnnotations === "function") refreshAnnotations();
  };
  $("viewer-actions").replaceChildren(button(current.asset.archived ? "Restore original" : "Archive original", async () => { if (typeof requireSavedMark === "function") requireSavedMark(); await flushNote(); await mutate(current.asset.archived ? "restore" : "archive", {assets: [current.asset.sha256]}); toast("File moved. Undo is available."); $("viewer").close(); current = null; }));
  if (typeof openReviewQueue === "function") $("viewer-actions").append(button("Review / nominate candidate", () => { requireSavedMark(); openReviewQueue(current.id); }));
  if (typeof editIteration === "function") $("viewer-actions").append(button("Record iteration", () => { requireSavedMark(); openHistory(current.asset.sha256); }));
  if (current.detail) $("viewer-actions").append(button("Delete detail view", async () => { if (typeof requireSavedMark === "function") requireSavedMark(); await flushNote(); await mutate("detail_delete", {id: current.id}); $("viewer").close(); current = null; toast("Detail view removed. Original unchanged; Undo available."); }));
  $("provenance").replaceChildren(element("p", "hash", "SHA-256 " + current.asset.sha256), element("p", "muted", current.asset.stored_filename), element("p", "muted", size(current.asset.size_bytes)));
  const link = element("a", "", "Open preserved original ↗"); link.href = current.asset.url; link.target = "_blank"; link.rel = "noopener"; $("provenance").append(link);
  if (current.detail) { $("provenance").append(element("p", "muted", "Normalized region: " + current.detail.rect.map(n => n.toFixed(4)).join(", "))); $("viewer-actions").append(button("Focus detail / show parent", () => focusDetail())); }
  if (!$("viewer").open) $("viewer").showModal();
  if ($("full-image").complete) { setZoom(); showRect(); }
  if (current.detail) focusDetail(true);
  if (typeof refreshAnnotations === "function") refreshAnnotations();
}
function setZoom() {
  const image = $("full-image"), stage = $("image-stage"), zoom = $("zoom").value;
  stage.style.overflow = ""; stage.style.maxWidth = "none";
  image.style.position = ""; image.style.left = ""; image.style.top = ""; image.style.width = ""; image.style.height = "";
  image.style.maxWidth = image.style.maxHeight = "none";
  if (image.naturalWidth && image.naturalHeight) {
    const scale = zoom === "fit" ? Math.min(1, ($("image-scroll").clientWidth - 30) / image.naturalWidth,
      ($("image-scroll").clientHeight - 30) / image.naturalHeight) : Number(zoom);
    stage.style.width = image.style.width = `${image.naturalWidth * scale}px`;
    stage.style.height = image.style.height = `${image.naturalHeight * scale}px`;
  }
  stage.dataset.focused = "false"; showRect();
  if (typeof renderAnnotations === "function") renderAnnotations();
}
function focusDetail(force = false) {
  if (!current?.detail) return;
  const image = $("full-image"), stage = $("image-stage");
  if (!image.naturalWidth) { image.addEventListener("load", () => focusDetail(true), {once: true}); return; }
  if (stage.dataset.focused === "true" && !force) { setZoom(); return; }
  const [l, t, r, b] = current.detail.rect, available = $("image-scroll").clientWidth - 30;
  const scale = Math.min(available / (image.naturalWidth * (r - l)), ($("image-scroll").clientHeight - 30) / (image.naturalHeight * (b - t)));
  stage.style.width = `${image.naturalWidth * (r - l) * scale}px`; stage.style.height = `${image.naturalHeight * (b - t) * scale}px`; stage.style.overflow = "hidden";
  image.style.maxWidth = image.style.maxHeight = "none"; image.style.position = "absolute";
  image.style.width = `${image.naturalWidth * scale}px`; image.style.height = `${image.naturalHeight * scale}px`;
  image.style.left = `${-l * image.naturalWidth * scale}px`; image.style.top = `${-t * image.naturalHeight * scale}px`;
  stage.dataset.focused = "true"; $("region-box").hidden = true;
  if (typeof renderAnnotations === "function") renderAnnotations();
}
function showRect() {
  const box = $("region-box"); box.hidden = !rect || $("image-stage").dataset.focused === "true";
  if (!rect) return;
  box.style.left = `${rect[0] * 100}%`; box.style.top = `${rect[1] * 100}%`; box.style.width = `${(rect[2] - rect[0]) * 100}%`; box.style.height = `${(rect[3] - rect[1]) * 100}%`;
  ["left", "top", "right", "bottom"].forEach((name, i) => { $("region-" + name).value = (rect[i] * 100).toFixed(2); });
}
function startRegion() {
  if (typeof requireSavedMark === "function") requireSavedMark();
  if (typeof resetAnnotations === "function") resetAnnotations();
  if (!$("full-image").naturalWidth) { toast("Wait for the original image to load before drawing."); return; }
  setZoom(); drawing = true; rect = [.2, .2, .8, .8]; $("image-stage").classList.add("drawing"); $("region-form").hidden = $("region-help").hidden = false; $("region-title").value = ""; showRect();
}
function stopRegion() { drawing = false; dragStart = null; $("image-stage").classList.remove("drawing"); $("region-form").hidden = $("region-help").hidden = true; rect = current?.detail ? [...current.detail.rect] : null; showRect(); }
function point(event) { const b = $("full-image").getBoundingClientRect(); return [Math.max(0, Math.min(1, (event.clientX - b.left) / b.width)), Math.max(0, Math.min(1, (event.clientY - b.top) / b.height))]; }
async function flushNote() {
  clearTimeout(noteTimer); const pending = pendingNote; pendingNote = null;
  if (!pending) return;
  try { await mutate("note", pending); $("note-status").textContent = "Saved locally · excluded from Git and publication"; }
  catch (error) { if (!pendingNote) pendingNote = pending; $("note-status").textContent = "Not saved — " + error.message; throw error; }
}
async function closeViewer() { if (typeof requireSavedMark === "function") requireSavedMark(); await flushNote(); $("viewer").close(); current = null; }
function openCompare() {
  if (typeof openAdvancedCompare === "function") return openAdvancedCompare();
  const list = [...selection].map(findItem); if (list.length !== 2) return;
  $("compare-grid").replaceChildren();
  for (const item of list) {
    const article = element("article"); article.append(element("p", "eyebrow", identity(item)), element("h3", "", item.title));
    const image = element("div", "comparison-image"); image.append(regionImage(item)); article.append(image);
    article.append(element("p", "hash", item.asset.sha256), scopeContent(item));
    article.append(button("Zoom / fit", () => image.classList.toggle("compare-zoomed")));
    article.append(button(item.asset.archived ? "Restore this original" : "Archive this original", async () => { await mutate(item.asset.archived ? "restore" : "archive", {assets: [item.asset.sha256]}); $("comparison").close(); toast("File moved. Undo is available."); }));
    $("compare-grid").append(article);
  }
  $("comparison").showModal();
}

function bind() {
  if (typeof bindAnnotations === "function") bindAnnotations();
  if (typeof bindComparisons === "function") bindComparisons();
  if (typeof bindIterations === "function") bindIterations();
  if (typeof bindReviewQueue === "function") bindReviewQueue();
  for (const id of ["search", "kind", "sort"]) $(id).addEventListener(id === "search" ? "input" : "change", render);
  $("new-collection").onclick = () => run(async () => { const name = await requestText("Create a feature collection"); if (name) { await mutate("collection_create", {name}); toast("Collection created. Add any images or detail views."); } });
  $("rename-collection").onclick = () => run(async () => { const c = collection(), name = await requestText("Rename collection", c.name); if (name) await mutate("collection_rename", {id: c.id, name}); });
  $("delete-collection").onclick = () => run(async () => { const id = collection().id; await mutate("collection_delete", {id}); view = "active"; render(); toast("Collection removed; images unchanged. Undo available."); });
  $("text-form").onsubmit = event => { event.preventDefault(); textDone($("text-value").value.trim()); };
  $("text-cancel").onclick = () => textDone(null); $("text-dialog").addEventListener("cancel", event => { event.preventDefault(); textDone(null); });
  $("undo").onclick = () => run(async () => { if (typeof requireSavedMark === "function") requireSavedMark(); await flushNote(); await mutate("undo"); if (typeof resetAnnotations === "function") { resetAnnotations(); refreshAnnotations(); } if (!state.public.collections.some(c => c.id === view) && !["active", "archive", "details", "unassigned"].includes(view)) view = "active"; render(); if (current) { memberships(current); $("private-note").value = state.notes[current.id] || ""; } toast("Last change undone."); });
  $("select-visible").onclick = () => { visible.forEach(item => selection.add(item.id)); render(); };
  $("clear-selection").onclick = () => { selection.clear(); render(); };
  $("add-selection").onclick = () => run(async () => { await mutate("collection_assign", {id: $("assign-collection").value, ...selectedItems()}); toast("Selection added to collection. Files stayed in place."); });
  $("remove-selection").onclick = () => run(() => mutate("collection_assign", {id: collection().id, ...selectedItems(), remove: true}));
  for (const [id, action] of [["archive-selection", "archive"], ["restore-selection", "restore"]]) $(id).onclick = () => run(async () => { const {assets} = selectedItems(); if (!assets.length) return; await mutate(action, {assets}); selection.clear(); render(); toast(`${assets.length} original file(s) ${action === "archive" ? "archived" : "restored"}. Undo available.`); });
  $("compare").onclick = openCompare; $("close-comparison").onclick = () => $("comparison").close();
  $("close-viewer").onclick = () => run(closeViewer); $("viewer").addEventListener("cancel", event => { event.preventDefault(); if (drawing) stopRegion(); else run(closeViewer); });
  $("zoom").onchange = setZoom; $("draw-region").onclick = startRegion; $("cancel-region").onclick = stopRegion;
  $("image-stage").addEventListener("pointerdown", event => { if (!drawing || event.button !== 0) return; dragStart = point(event); $("image-stage").setPointerCapture(event.pointerId); event.preventDefault(); });
  $("image-stage").addEventListener("pointermove", event => { if (!drawing || !dragStart) return; const p = point(event); rect = [Math.min(p[0], dragStart[0]), Math.min(p[1], dragStart[1]), Math.max(p[0], dragStart[0]), Math.max(p[1], dragStart[1])]; showRect(); });
  $("image-stage").addEventListener("pointerup", () => { dragStart = null; }); $("image-stage").addEventListener("pointercancel", () => { dragStart = null; });
  for (const name of ["left", "top", "right", "bottom"]) $("region-" + name).onchange = () => { rect = ["left", "top", "right", "bottom"].map(n => Number($("region-" + n).value) / 100); showRect(); };
  $("save-region").onclick = () => run(async () => { if (!rect || rect[2] <= rect[0] || rect[3] <= rect[1]) throw new Error("Draw a region with positive width and height."); const title = $("region-title").value.trim(); if (!title) throw new Error("Give this public detail view a title."); await mutate("detail_save", {asset_sha256: current.asset.sha256, title, rect: rect.map(n => Number(n.toFixed(6)))}); stopRegion(); toast("Detail view saved. Original pixels unchanged."); });
  $("private-note").oninput = () => { pendingNote = {id: current.id, text: $("private-note").value}; $("note-status").textContent = "Saving locally…"; clearTimeout(noteTimer); noteTimer = setTimeout(() => run(flushNote), 500); };
  window.addEventListener("beforeunload", event => { if (pendingNote) { event.preventDefault(); event.returnValue = ""; } });
}
async function init() {
  try { const response = await fetch("/api/state"); const value = await response.json(); if (!response.ok) throw new Error(value.error); state = value; token = value.token; bind(); render(); }
  catch (error) { $("library-summary").textContent = "Could not load the checkout"; toast(error.message); }
}
init();
