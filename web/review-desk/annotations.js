"use strict";
const MARK_FEATURES = ["cap", "lichen", "face", "eyes", "tissue", "arms-hands", "legs", "locomotion", "baseline-skirt", "membrane", "pose", "other"];
let markDraft = null, markDirty = false, markDrag = null;
function marks() { return state.workspace?.annotations || []; }
function svgNode(tag, attrs = {}) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
  return node;
}
function markSvg(mark, width, height) {
  const points = mark.points.map(p => [p[0] * width, p[1] * height]);
  const [a, b = a] = points, attrs = {"vector-effect": "non-scaling-stroke", fill: "none"};
  let node;
  if (mark.kind === "rectangle") node = svgNode("rect", {...attrs, x: Math.min(a[0], b[0]), y: Math.min(a[1], b[1]), width: Math.abs(b[0] - a[0]), height: Math.abs(b[1] - a[1])});
  if (mark.kind === "ellipse") node = svgNode("ellipse", {...attrs, cx: (a[0]+b[0])/2, cy: (a[1]+b[1])/2, rx: Math.abs(b[0]-a[0])/2, ry: Math.abs(b[1]-a[1])/2});
  if (mark.kind === "pin") node = svgNode("circle", {...attrs, cx: a[0], cy: a[1], r: Math.min(width, height)*.012});
  if (mark.kind === "arrow" || mark.kind === "freehand") {
    let path = points.map((p,i) => (i ? "L" : "M") + p.join(",")).join(" ");
    if (mark.kind === "arrow") {
      const angle = Math.atan2(b[1]-a[1], b[0]-a[0]), length = Math.min(width,height)*.03;
      for (const delta of [-.5,.5]) path += " M" + [b[0]-length*Math.cos(angle+delta), b[1]-length*Math.sin(angle+delta)].join(",") + " L" + b.join(",");
    }
    node = svgNode("path", {...attrs, d:path});
  }
  node.dataset.mark = mark.id || "draft"; node.classList.add("annotation-mark", "severity-" + mark.severity);
  if (["resolved","dismissed"].includes(mark.status)) node.classList.add("mark-resolved");
  const title = svgNode("title"); title.textContent = mark.feature + ": " + mark.comment; node.append(title);
  return node;
}
function renderAnnotations() {
  const layer = $("annotation-layer");
  if (!layer || !current) return;
  const image = $("full-image"), width = image.naturalWidth, height = image.naturalHeight;
  if (!width || !height) return;
  layer.setAttribute("viewBox", "0 0 " + width + " " + height);
  layer.style.width = image.style.width; layer.style.height = image.style.height;
  layer.style.left = image.style.left || "0px"; layer.style.top = image.style.top || "0px";
  layer.replaceChildren();
  for (const mark of marks().filter(a => a.target === current.id && a.id !== markDraft?.id)) layer.append(markSvg(mark,width,height));
  if (markDraft) {
    layer.append(markSvg(markDraft,width,height));
    const handles = markDraft.kind === "freehand" ? [0, markDraft.points.length-1] : markDraft.points.map((_,i)=>i);
    for (const i of handles) {
      const point = markDraft.points[i];
      const handle = svgNode("circle", {cx: point[0]*width, cy: point[1]*height, r:Math.min(width,height)*.014, "vector-effect":"non-scaling-stroke"});
      handle.classList.add("mark-handle"); handle.dataset.handle = String(i); layer.append(handle);
    }
  }
  layer.classList.toggle("mark-drawing", Boolean($("mark-tool").value));
}
function draftForm() {
  $("annotation-form").hidden = !markDraft;
  if (markDraft) {
    $("mark-comment").value = markDraft.comment; $("mark-feature").value = markDraft.feature;
    $("mark-severity").value = markDraft.severity; $("mark-status").value = markDraft.status;
    $("mark-points").value = JSON.stringify(markDraft.points); $("delete-mark").disabled = !markDraft.id;
  }
  $("mark-save-state").textContent = markDirty ? "Unsaved edit · Save or cancel before closing" : "";
  renderAnnotations();
}
function refreshAnnotations() {
  if (!$("annotation-list") || !current) return;
  $("annotation-list").replaceChildren(...marks().filter(a=>a.target===current.id).map(a=>{
    const node = button(a.feature + " · " + a.severity + " · " + a.status + " — " + (a.comment || a.kind), ()=>{
      requireSavedMark(); markDraft = structuredClone(a); markDirty = false; $("mark-tool").value = ""; draftForm();
    }, "annotation-entry");
    node.dataset.markId = a.id; return node;
  }));
  draftForm();
}
function resetAnnotations() {
  markDraft = null; markDirty = false; markDrag = null;
  if ($("mark-tool")) $("mark-tool").value = "";
  if ($("annotation-form")) $("annotation-form").hidden = true;
  renderAnnotations();
}
function requireSavedMark() { if (markDirty) throw new Error("Save or cancel the annotation edit first."); }
function beginMark() {
  requireSavedMark();
  if (!$("full-image").naturalWidth) throw new Error("Wait for the original to load.");
  stopRegion(); setZoom(); markDraft = null; markDrag = null;
  if (!$("mark-tool").value) $("mark-tool").value = "rectangle";
  draftForm();
}
function bindAnnotations() {
  $("mark-feature").replaceChildren(...MARK_FEATURES.map(value=>{const o=element("option","",value); o.value=value; return o;}));
  $("annotation-form").hidden = true;
  $("new-mark").onclick = ()=>run(beginMark);
  $("mark-tool").onchange = ()=>run(()=>{ requireSavedMark(); if ($("mark-tool").value) beginMark(); else renderAnnotations(); });
  for (const key of ["comment","feature","severity","status","points"]) $("mark-"+key).addEventListener("input",()=>{
    if (!markDraft) return;
    if (key !== "points") markDraft[key] = $("mark-"+key).value;
    markDirty = true; $("mark-save-state").textContent = "Unsaved edit"; renderAnnotations();
  });
  $("annotation-form").onsubmit = event=>{
    event.preventDefault();
    run(async ()=>{
      if (!markDraft) throw new Error("Draw a mark first.");
      const record = {...markDraft, points:JSON.parse($("mark-points").value)};
      await flushNote(); await mutate("annotation_save",{record}); resetAnnotations(); refreshAnnotations(); toast("Annotation saved privately. Undo is available.");
    });
  };
  $("delete-mark").onclick = ()=>run(async ()=>{
    if (!markDraft?.id) return; await flushNote(); await mutate("annotation_delete",{id:markDraft.id}); resetAnnotations(); refreshAnnotations();
  });
  $("cancel-mark").onclick = ()=>{resetAnnotations(); refreshAnnotations();};
  const layer = $("annotation-layer");
  layer.addEventListener("pointerdown", event=>run(()=>{
    if (event.button !== 0 || drawing) return;
    const p = point(event), tool = $("mark-tool").value;
    if (tool) {
      requireSavedMark();
      markDraft = {target:current.id,kind:tool,points:tool==="pin"?[p]:[p,p],comment:"",feature:"other",severity:"info",status:"open"};
      markDrag = {mode:"draw"}; markDirty = true;
    } else {
      const handle = event.target.dataset.handle, selected = event.target.dataset.mark;
      if (handle !== undefined && markDraft) markDrag = {mode:"handle",index:Number(handle)};
      else if (selected) {
        if (selected !== (markDraft?.id || "draft")) {
          requireSavedMark(); markDraft = structuredClone(marks().find(a=>a.id===selected));
        }
        if (!markDraft) return;
        markDrag = {mode:"move",start:p,points:structuredClone(markDraft.points)};
      } else return;
    }
    layer.setPointerCapture(event.pointerId); event.preventDefault(); draftForm();
  }));
  layer.addEventListener("pointermove", event=>{
    if (!markDrag || !markDraft) return;
    const p = point(event);
    if (markDrag.mode === "draw") {
      if (markDraft.kind === "freehand") { if (markDraft.points.length<2048) markDraft.points.push(p); }
      else if (markDraft.kind !== "pin") markDraft.points[1] = p;
    } else if (markDrag.mode === "handle") markDraft.points[markDrag.index] = p;
    else {
      const xs=markDrag.points.map(p=>p[0]), ys=markDrag.points.map(p=>p[1]);
      const dx=Math.max(-Math.min(...xs),Math.min(1-Math.max(...xs),p[0]-markDrag.start[0]));
      const dy=Math.max(-Math.min(...ys),Math.min(1-Math.max(...ys),p[1]-markDrag.start[1]));
      markDraft.points = markDrag.points.map(q=>[q[0]+dx,q[1]+dy]);
    }
    markDirty = true; draftForm();
  });
  layer.addEventListener("pointerup",()=>{
    if (markDrag?.mode === "draw") $("mark-tool").value = "";
    markDrag=null; draftForm();
  });
  layer.addEventListener("pointercancel",()=>{markDrag=null; draftForm();});
  window.addEventListener("resize",renderAnnotations);
  window.addEventListener("beforeunload",event=>{if(markDirty){event.preventDefault();event.returnValue="";}});
}
