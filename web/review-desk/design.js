"use strict";
// Idea history is private; the existing artwork library remains the source of every image.
let designStaged=[],designChoices={},designBase=null,designMerge=null,designSelected=null,designDirty=false;
function designModel(){return state.workspace?.design||{ideas:[],branches:[],nodes:[],checkpoints:[],head:null,metadata:{},audit:[]};}
function designMap(key){return new Map(designModel()[key].map(v=>[v.id,v]));}
function designContext(route="mainline"){
  const model=designModel(),cps=designMap("checkpoints"),context=structuredClone(cps.get(model.head)?.selections||{});
  if(route!=="mainline"){
    const branch=designMap("branches").get(route),origin=cps.get(branch?.head||branch?.base);
    if(origin?.selections[branch.idea_id])context[branch.idea_id]=origin.selections[branch.idea_id];
  }
  return context;
}
function designOptions(id,values,selected=null,multiple=false){
  const select=$(id),old=selected===null?[...select.selectedOptions].map(o=>o.value):selected;
  select.replaceChildren(...values.map(([value,label])=>{const option=element("option","",label);option.value=value;option.selected=old.includes(value);return option;}));
  if(!multiple&&!select.value&&select.options.length)select.options[0].selected=true;
}
function renderDesign(){
  if(!$("design-lanes"))return;
  const model=designModel(),nodes=designMap("nodes"),ideas=designMap("ideas");
  $("design-summary").textContent=model.ideas.length+" ideas · "+model.nodes.length+" iterations · "+model.checkpoints.length+" checkpoints · working choices grant no canon approval";
  designOptions("design-idea",model.ideas.map(i=>[i.id,i.name]));
  designOptions("branch-idea",model.ideas.map(i=>[i.id,i.name]));
  designOptions("branch-parents",model.branches.map(b=>[b.id,ideas.get(b.idea_id).name+" / "+b.name]),null,true);
  designOptions("branch-base",[["","Latest working checkpoint"],...model.checkpoints.map(c=>[c.id,c.name])]);
  designOptions("design-route",[["mainline","Working mainline"],...model.branches.map(b=>[b.id,ideas.get(b.idea_id).name+" / "+b.name+(b.experimental?" · experimental":"")])]);
  refreshDesignDraftOptions();
  renderDesignStages();
  const timeline=$("design-lanes"),header=element("div","design-time-header");
  header.append(element("strong","design-lane-label","Idea / direction"));
  for(const cp of model.checkpoints){const column=button(cp.name+" · "+cp.updates.length+" new",()=>inspectCheckpoint(cp.id),"checkpoint-column");if(cp.updates.length>1)column.classList.add("shared-checkpoint");header.append(column);}
  const content=element("div","design-time-content");content.append(header);
  
  for(const idea of model.ideas){
    const group=element("details","idea-container");
    group.open=!collapsedIdeas.has(idea.id);
    const summary=element("summary","",idea.name+(idea.experimental?" · experimental":""));
    group.append(summary);group.addEventListener("toggle",()=>{group.open?collapsedIdeas.delete(idea.id):collapsedIdeas.add(idea.id);requestAnimationFrame(redraw);});
    const lanes=[{id:"mainline",name:"Working design"},...model.branches.filter(b=>b.idea_id===idea.id)];
    for(const lane of lanes){
      const line=element("div","design-lane"),label=element("div","design-lane-label");
      label.append(element("strong","",lane.name),element("small","muted",lane.experimental?"Experimental direction":"Development direction"));
      if(lane.parents?.length)label.append(element("small","muted","Derived from "+lane.parents.map(id=>designMap("branches").get(id).name).join(", ")));
      label.append(button("Iterate",()=>{if(designDirty)throw new Error("Stage or discard the draft first.");setDesignRoute(lane.id);$("design-idea").value=idea.id;resetDesignDraft();},"compact"));
      line.append(label);let carried=null;
      for(let index=0;index<model.checkpoints.length;index++){
        const cp=model.checkpoints[index],cell=element("div","design-time-cell");cell.dataset.checkpoint=cp.id;cell.dataset.route=lane.id;
        const born=cp.updates.map(id=>nodes.get(id)).find(n=>n.idea_id===idea.id&&(n.branch_id||"mainline")===lane.id);
        if(cp.route===lane.id&&cp.selections[idea.id])carried=cp.selections[idea.id];
        if(born){
          const meta=model.metadata[born.id],card=button("",()=>inspectDesignNode(born.id),"design-node");
          card.dataset.node=born.id;card.append(element("strong","",born.title),element("small","",meta.outcome+" · "+meta.lifecycle));
          if(meta.candidate)card.append(element("small","badge candidate","Nominated · no canon approval"));
          const target=born.targets.map(findItem).find(Boolean);
          if(target){const preview=element("div","design-preview");preview.append(regionImage(target));card.prepend(preview);}
          cell.append(card);
        }else if(carried){
          const ref=nodes.get(carried);cell.classList.add("carried-version");
          cell.append(button("Continue: "+ref.title,()=>inspectDesignNode(ref.id),"carried-label"));
        }
        if(cp.route===lane.id&&cp.selections[idea.id]&&!cp.updates.includes(cp.selections[idea.id])){
          const selected=nodes.get(cp.selections[idea.id]);
          if(!born)cell.append(element("small","selection-label","Selected existing version"));
          if(selected?.branch_id&&lane.id==="mainline"){cell.classList.add("adopted-version");cell.dataset.adopted=selected.id;}
        }
        line.append(cell);
      }
      group.append(line);
    }
    content.append(group);
  }
  const edges=svgNode("svg",{class:"design-edges","aria-hidden":"true"});
  content.append(edges);timeline.replaceChildren(content);
  const redraw=()=>{
    edges.replaceChildren();const origin=content.getBoundingClientRect(),seen=new Set();
    const connect=(start,end,color="#90b991")=>{
      if(!start||!end||!start.getClientRects().length||!end.getClientRects().length)return;
      const key=start.dataset.node+"-"+(end.dataset.node||end.dataset.checkpoint)+"-"+end.dataset.route;
      if(seen.has(key))return;seen.add(key);
      const p=start.getBoundingClientRect(),e=end.getBoundingClientRect();
      const x1=p.left-origin.left+p.width/2,y1=p.top-origin.top+p.height/2,x2=e.left-origin.left+e.width/2,y2=e.top-origin.top+e.height/2;
      edges.append(svgNode("path",{d:`M${x1},${y1} C${(x1+x2)/2},${y1} ${(x1+x2)/2},${y2} ${x2},${y2}`,fill:"none",stroke:color,"stroke-width":2}));
    };
    const card=id=>content.querySelector('[data-node="'+id+'"]');
    for(const node of model.nodes)for(const parent of node.parents)connect(card(parent),card(node.id),designMap("branches").get(node.branch_id)?.experimental?"#deaa74":"#90b991");
    for(const branch of model.branches){
      const first=model.nodes.find(n=>n.branch_id===branch.id);if(!first)continue;
      const base=designMap("checkpoints").get(branch.base);
      if(base?.selections[branch.idea_id])connect(card(base.selections[branch.idea_id]),card(first.id),branch.experimental?"#deaa74":"#90b991");
      for(const parent of branch.parents){
        const sourceBranch=designMap("branches").get(parent),source=designMap("checkpoints").get(sourceBranch.head||sourceBranch.base);
        if(source?.selections[sourceBranch.idea_id])connect(card(source.selections[sourceBranch.idea_id]),card(first.id),branch.experimental?"#deaa74":"#90b991");
      }
    }
    for(const cell of content.querySelectorAll("[data-adopted]"))connect(card(cell.dataset.adopted),cell,"#deaa74");
    edges.setAttribute("height",content.scrollHeight);edges.setAttribute("width",content.scrollWidth);
  };
  requestAnimationFrame(redraw);
  if(!model.ideas.length)timeline.append(element("p","empty","Create an idea container, then record its first iteration. Existing artwork and collections are available to attach."));
  const unassigned=$("design-unassigned");unassigned.replaceChildren();
  for(const legacy of state.workspace?.iterations||[]){
    const row=element("div","unassigned-row");
    row.append(element("span","",legacy.title+" · "+legacy.relationship),button("Link to an idea",()=>{
      resetDesignDraft();$("design-title").value=legacy.title;
      for(const field of ["prompt","corrections"])$("design-"+field).value=legacy[field];
      designOptions("design-targets",items().map(i=>[i.id,identity(i)+" · "+i.title]),[legacy.asset_sha256],true);
      $("design-form").dataset.legacy=legacy.id;designDirty=true;
      $("design-form").scrollIntoView({block:"center"});
    }));
    if(model.nodes.some(n=>n.legacy_id===legacy.id))row.append(element("small","muted","Linked; original record retained"));
    unassigned.append(row);
  }
  if(!unassigned.children.length)unassigned.append(element("p","muted","No unassigned iteration records."));
}
const collapsedIdeas=new Set();
function refreshDesignDraftOptions(){
  const model=designModel(),idea=$("design-idea").value;
  designOptions("design-branch",[["","Working direction"],...model.branches.filter(b=>b.idea_id===idea).map(b=>[b.id,b.name+(b.experimental?" · experimental":"")])]);
  designOptions("design-targets",items().map(i=>[i.id,identity(i)+" · "+i.title]),null,true);
  designOptions("design-parents",model.nodes.filter(n=>n.idea_id===idea).map(n=>[n.id,n.title]),null,true);
}
function setDesignRoute(route){
  if(route!==$("design-route").value&&(designDirty||designStaged.length||Object.keys(designChoices).length))throw new Error("Record or discard staged changes before changing route.");
  $("design-route").value=route;designLastRoute=route;
  if(route!=="mainline"){
    const branch=designMap("branches").get(route);$("design-idea").value=branch.idea_id;
    refreshDesignDraftOptions();$("design-branch").value=route;
  }
}
function resetDesignDraft(node=null){
  refreshDesignDraftOptions();
  const context=designContext($("design-route").value),parents=node?[node.id]:context[$("design-idea").value]?[context[$("design-idea").value]]:[];
  for(const field of ["title","prompt","corrections"])$("design-"+field).value=node?node[field]:"";
  designOptions("design-targets",items().map(i=>[i.id,identity(i)+" · "+i.title]),node?.targets||[],true);
  designOptions("design-parents",designModel().nodes.filter(n=>n.idea_id===$("design-idea").value).map(n=>[n.id,n.title]),parents,true);
  $("design-form").dataset.legacy="";designDirty=false;renderContributions();
}
function renderContributions(){
  const box=$("design-contributions"),previous=new Map([...box.querySelectorAll("textarea")].map(t=>[t.dataset.parent,t.value]));
  box.replaceChildren();
  const parents=[...$("design-parents").selectedOptions];
  if(parents.length<2)return;
  for(const parent of parents){
    const label=element("label","", "Take from "+parent.textContent),text=element("textarea");text.rows=2;text.maxLength=20000;text.required=true;text.dataset.parent=parent.value;text.value=previous.get(parent.value)||"";
    label.append(text);box.append(label);
  }
}
function stageDesignNode(){
  const idea=$("design-idea").value;if(!idea)throw new Error("Create an idea container first.");
  const title=$("design-title").value.trim();if(!title)throw new Error("Give the iteration a title.");
  const node={idea_id:idea,branch_id:$("design-branch").value||null,title,
    targets:[...$("design-targets").selectedOptions].map(o=>o.value),prompt:$("design-prompt").value,
    corrections:$("design-corrections").value,parents:[...$("design-parents").selectedOptions].map(o=>o.value),
    contributions:[...document.querySelectorAll("#design-contributions textarea")].map(t=>({node_id:t.dataset.parent,detail:t.value})),
    legacy_id:$("design-form").dataset.legacy||null};
  if(node.contributions.some(c=>!c.detail.trim()))throw new Error("Describe what comes from each combined parent.");
  const route=$("design-route").value;
  if(route!=="mainline"&&(designMap("branches").get(route).idea_id!==idea||node.branch_id!==route))throw new Error("This direction changes only its own idea.");
  designStaged=designStaged.filter(n=>n.idea_id!==idea);designStaged.push(node);delete designChoices[idea];
  resetDesignDraft();renderDesignStages();toast("Iteration staged. Record the checkpoint to save it.");
}
function renderDesignStages(){
  const box=$("design-staged");box.replaceChildren();
  const ideas=designMap("ideas"),nodes=designMap("nodes");
  for(const node of designStaged)box.append(element("p","",ideas.get(node.idea_id)?.name+": new iteration — "+node.title),button("Remove staged "+node.title,()=>{designStaged=designStaged.filter(n=>n!==node);renderDesignStages();}));
  for(const [idea,id] of Object.entries(designChoices))box.append(element("p","",ideas.get(idea)?.name+": select existing — "+nodes.get(id)?.title));
  if(designBase)box.append(element("p","muted","Restore choices from "+designMap("checkpoints").get(designBase)?.name+" as a new checkpoint."));
  if(!box.children.length)box.append(element("p","muted","Stage one or several idea changes. Unchanged versions carry forward."));
}
async function recordDesignCheckpoint(){
  if(designDirty)throw new Error("Stage or discard the iteration draft first.");
  const name=$("checkpoint-name").value.trim();if(!name)throw new Error("Name this checkpoint.");
  const selections={...designChoices};designStaged.forEach((n,i)=>selections[n.idea_id]="$"+i);
  await mutate("design_checkpoint",{name,route:$("design-route").value,nodes:designStaged,selections,base:designBase,merge:designMerge});
  designStaged=[];designChoices={};designBase=null;designMerge=null;$("checkpoint-name").value="";renderDesign();resetDesignDraft();
  toast("Checkpoint saved privately · Undo available · no canon approval");
}
function inspectCheckpoint(id){
  if(designReviewDirty)throw new Error("Save or cancel the iteration review first.");
  const cp=designMap("checkpoints").get(id),box=$("design-inspector");designSelected=null;
  box.replaceChildren(element("h3","",cp.name),element("p","muted","Recorded "+cp.created_at+" · "+(cp.route==="mainline"?"working mainline":"branch checkpoint")));
  for(const [idea,node] of Object.entries(cp.selections))box.append(button(designMap("ideas").get(idea).name+": "+designMap("nodes").get(node).title,()=>inspectDesignNode(node)));
  box.append(button("Restore these choices as a new checkpoint",()=>{
    if(designStaged.length||Object.keys(designChoices).length||designDirty)throw new Error("Record or discard staged changes first.");
    designBase=id;setDesignRoute("mainline");renderDesignStages();
  }),button("Start a direction from here",()=>{$("branch-base").value=id;$("branch-form").open=true;$("branch-form").scrollIntoView({block:"center"});}));
  box.scrollIntoView({block:"nearest"});
}
function inspectDesignNode(id){
  const model=designModel(),node=designMap("nodes").get(id);if(!node)throw new Error("Unknown iteration.");
  if(designReviewDirty)throw new Error("Save or cancel the current iteration review.");
  designSelected=id;const meta=model.metadata[id],idea=designMap("ideas").get(node.idea_id),box=$("design-inspector");
  box.replaceChildren(element("h3","",idea.name+" / "+node.title),element("p","muted","Recorded design content stays fixed. A revision creates a new node."));
  box.append(button("Revise this iteration",()=>{if(designDirty)throw new Error("Stage or discard the draft first.");setDesignRoute("mainline");$("design-idea").value=node.idea_id;refreshDesignDraftOptions();$("design-branch").value=node.branch_id||"";resetDesignDraft(node);$("design-form").scrollIntoView({block:"center"});}),
    button("Select this version on mainline",()=>{setDesignRoute("mainline");designChoices[node.idea_id]=id;designStaged=designStaged.filter(n=>n.idea_id!==node.idea_id);designMerge=designModel().checkpoints.find(c=>c.updates.includes(id))?.id||null;renderDesignStages();}));
  const combined=[...new Set([...node.targets,...node.parents.flatMap(p=>designMap("nodes").get(p).targets)])];
  if(combined.length>=2)box.append(button("Compare with parent artwork",()=>{selection=new Set(combined.slice(0,4));return openCompare();}));
  for(const target of node.targets){
    const item=findItem(target);if(!item)continue;
    box.append(button("Inspect / annotate "+identity(item),()=>openViewer(target)),scopeContent(item));
  }
  for(const [label,text] of [["Requested corrections",node.corrections],["Prompt",node.prompt],...node.contributions.map(c=>["Contribution from "+designMap("nodes").get(c.node_id).title,c.detail])]){
    if(text){const details=element("details"),summary=element("summary","",label);details.append(summary,element("p","",text));box.append(details);}
  }
  const form=element("form");form.id="design-review-form";
  for(const [field,values] of [["outcome",["unreviewed","needs-refinement","reviewed","rejected"]],["lifecycle",["current","legacy","obsolete"]]]){
    const label=element("label","",field==="outcome"?"Review outcome":"History label"),select=element("select");select.id="design-review-"+field;
    for(const value of values){const option=element("option","",value);option.value=value;option.selected=meta[field]===value;select.append(option);}label.append(select);form.append(label);
  }
  for(const [field,labelText] of [["notes","Private notes / metadata corrections"],["nomination_reason","Candidate nomination reason"]]){
    const label=element("label","",labelText),text=element("textarea");text.id="design-review-"+field;text.rows=3;text.maxLength=20000;text.value=meta[field];label.append(text);form.append(label);
  }
  const label=element("label"),check=element("input");check.type="checkbox";check.id="design-review-candidate";check.checked=meta.candidate;label.append(check,document.createTextNode(" Nominate for review · no canon approval"));form.append(label);
  const save=element("button","primary","Save audited review");save.type="submit";form.append(save,button("Cancel review edit",()=>{designReviewDirty=false;inspectDesignNode(id);}));
  form.append(element("p","muted","Legacy and obsolete labels leave original files in place. Canon approval still uses the authenticated GitHub workflow."));
  form.oninput=()=>{designReviewDirty=true;};
  form.onsubmit=e=>{e.preventDefault();run(async()=>{
    const record={};for(const field of ["outcome","lifecycle","notes","nomination_reason"])record[field]=$("design-review-"+field).value;
    record.candidate=$("design-review-candidate").checked;
    await mutate("design_metadata",{id,record});designReviewDirty=false;inspectDesignNode(id);toast("Review saved with audit trail · Undo available");
  });};
  box.append(form,element("p","muted",model.audit.filter(a=>a.node_id===id).length+" audited metadata changes"));
  box.scrollIntoView({block:"nearest"});
}
let designReviewDirty=false;
function renderDesignQueue(){
  const box=$("design-queue-results");if(!box)return;
  box.replaceChildren();const model=designModel(),ideas=designMap("ideas");
  for(const node of model.nodes){
    const meta=model.metadata[node.id],idea=ideas.get(node.idea_id),lane=$("queue-lane").value;
    const status=meta.outcome==="reviewed"||meta.outcome==="rejected"?"completed":meta.outcome;
    const marksForNode=(state.workspace?.annotations||[]).filter(a=>node.targets.includes(a.target));
    const unresolved=marksForNode.filter(a=>["open","in-progress"].includes(a.status));
    if(lane==="candidates"&&!meta.candidate||lane==="unreviewed"&&status!=="unreviewed"||lane==="completed"&&status!=="completed"||lane==="refinement"&&status!=="needs-refinement"||lane==="unresolved"&&!unresolved.length)continue;
    if($("queue-feature").value&&$("queue-feature").value!==idea.feature)continue;
    if($("queue-family").value&&$("queue-family").value!==idea.family)continue;
    if($("queue-status").value&&$("queue-status").value!==status)continue;
    if($("queue-severity").value&&!(unresolved.length?unresolved.map(a=>a.severity):["info"]).includes($("queue-severity").value))continue;
    if(!$("queue-archived").checked&&node.targets.length&&node.targets.every(t=>findItem(t)?.asset.archived))continue;
    const card=element("article","design-queue-card");card.append(element("h3","",idea.name+" / "+node.title),element("p","muted",meta.outcome+" · "+meta.lifecycle+(idea.experimental?" · experimental":"")+(meta.candidate?" · nominated · no canon approval":"")),
      button("Review idea iteration",()=>{if(reviewDirty)throw new Error("Save or cancel the artwork review first.");$("queue-dialog").close();$("design-workspace").hidden=false;inspectDesignNode(node.id);}));
    box.append(card);
  }
}
function bindDesign(){
  designOptions("idea-feature",MARK_FEATURES.map(f=>[f,f]),["other"]);
  designOptions("idea-family",EXPERIMENT_FAMILY.map(f=>[f,f]),["none"]);
  $("idea-create-form").onsubmit=e=>{e.preventDefault();run(async()=>{
    await mutate("idea_create",{record:{name:$("idea-name").value,feature:$("idea-feature").value,family:$("idea-family").value,experimental:$("idea-experimental").checked}});
    $("idea-name").value="";$("design-idea").value=designModel().ideas.at(-1).id;resetDesignDraft();
  });};
  $("branch-create-form").onsubmit=e=>{e.preventDefault();run(async()=>{
    await mutate("branch_create",{record:{idea_id:$("branch-idea").value,name:$("branch-name").value,experimental:$("branch-experimental").checked,
      parents:[...$("branch-parents").selectedOptions].map(o=>o.value),base:$("branch-base").value||designModel().head}});
    $("branch-name").value="";setDesignRoute(designModel().branches.at(-1).id);resetDesignDraft();
  });};
  $("design-form").oninput=()=>{designDirty=true;};
  $("design-form").onsubmit=e=>{e.preventDefault();run(stageDesignNode);};
  $("design-discard-draft").onclick=()=>resetDesignDraft();
  $("design-parents").onchange=renderContributions;
  $("design-idea").onchange=()=>{refreshDesignDraftOptions();resetDesignDraft();};
  $("design-route").onchange=()=>{if(designStaged.length||Object.keys(designChoices).length||designDirty){toast("Discard or record staged changes before changing route.");$("design-route").value=designLastRoute;return;}setDesignRoute($("design-route").value);designLastRoute=$("design-route").value;resetDesignDraft();};
  $("checkpoint-record").onclick=()=>run(recordDesignCheckpoint);
  $("checkpoint-discard").onclick=()=>{designStaged=[];designChoices={};designBase=null;designMerge=null;resetDesignDraft();renderDesignStages();};
  $("design-open").onclick=()=>{$("design-workspace").hidden=!$("design-workspace").hidden;};
  window.addEventListener("beforeunload",e=>{if(designDirty||designStaged.length||Object.keys(designChoices).length||designReviewDirty){e.preventDefault();e.returnValue="";}});
  renderDesign();
}
let designLastRoute="mainline";
