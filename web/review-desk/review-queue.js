"use strict";
const WORKFLOW_STATUS=["unreviewed","in-progress","needs-refinement","completed"];
const REVIEW_SEVERITY=["info","minor","major","critical"];
const EXPERIMENT_FAMILY=["none","layered-petal","single-sheet","vascular","gill-frill","veil-streamer","spore-lace","shelf-fungus","lily-bud","mixed","other"];
let reviewDraft=null,reviewDirty=false;
function reviewRecords(){return state.workspace?.reviews||[];}
function reviewRows(){return state.review_queue||[];}
function populateOptions(id,values,all=false){
  const entries=all?[["","All"],...values.map(v=>[v,v])]:values.map(v=>[v,v]);
  $(id).replaceChildren(...entries.map(([id,label])=>{const o=element("option","",label);o.value=id;return o;}));
}
function openReviewQueue(id=null){
  if(reviewDirty)throw new Error("Save or cancel the current review edit first.");
  if(!$("queue-dialog").open)$("queue-dialog").showModal();
  renderReviewQueue();if(id)editReview(id);else{$("review-form").hidden=true;reviewDraft=null;}
}
function queueMatches(row){
  if(row.archived&&!$("queue-archived").checked)return false;
  const lane=$("queue-lane").value;
  if(lane==="unreviewed"&&row.workflow_status!=="unreviewed")return false;
  if(lane==="unresolved"&&!row.unresolved_annotations)return false;
  if(lane==="refinement"&&!row.needs_refinement)return false;
  if(lane==="candidates"&&!row.candidate)return false;
  if(lane==="completed"&&row.workflow_status!=="completed")return false;
  for(const [field,list] of [["feature","features"],["severity","severities"],["family","families"]]){
    const value=$("queue-"+field).value;if(value&&!row[list].includes(value))return false;
  }
  return !$("queue-status").value||row.workflow_status===$("queue-status").value;
}
function renderReviewQueue(){
  if(typeof renderDesignQueue==="function")renderDesignQueue();
  const rows=reviewRows().filter(queueMatches),cards=[];
  for(const row of rows){
    const item=findItem(row.target);if(!item)continue;
    const article=element("article","image-card queue-card");article.dataset.target=item.id;
    const preview=element("div","queue-preview");preview.append(regionImage(item));
    article.append(preview,element("p","card-id",identity(item)),element("h3","card-title",item.title));
    const badges=element("div","badges");
    badges.append(element("span","badge","Workflow: "+row.workflow_status));
    if(row.candidate)badges.append(element("span","badge candidate","Nominated · no canon approval"));
    if(row.unresolved_annotations)badges.append(element("span","badge",row.unresolved_annotations+" unresolved marks"));
    if(isExperimental(item.asset))badges.append(element("span","badge experiment","Experimental"));
    if(row.archived)badges.append(element("span","badge archived","Archived"));
    article.append(badges);
    article.append(element("p","muted",row.features.join(", ")+" · "+row.families.join(", ")));
    article.append(button("Review / nominate",()=>editReview(item.id),"queue-review"));
    article.append(button("Inspect image / annotations",()=>{
      if(reviewDirty)throw new Error("Save or cancel the current review edit first.");
      $("queue-dialog").close();return openViewer(item.id);
    }));
    cards.push(article);
  }
  $("queue-results").replaceChildren(...cards);$("queue-count").textContent=rows.length+" queue items";
  if(!cards.length)$("queue-results").append(element("p","empty","No items match these review filters."));
}
function editReview(id){
  if(reviewDirty)throw new Error("Save or cancel the current review edit first.");
  const item=findItem(id);if(!item)throw new Error("Unknown image or region.");
  const stored=reviewRecords().find(r=>r.target===id);
  reviewDraft=stored?structuredClone(stored):{target:id,workflow_status:"unreviewed",feature:"other",severity:"info",family:"none",candidate:false,nomination_reason:""};
  $("review-form").hidden=false;$("review-target-title").textContent=identity(item)+" · "+item.title;
  $("review-status").value=reviewDraft.workflow_status;$("review-feature").value=reviewDraft.feature;
  $("review-severity").value=reviewDraft.severity;$("review-family").value=reviewDraft.family;
  $("review-candidate").checked=reviewDraft.candidate;$("review-reason").value=reviewDraft.nomination_reason;
  $("review-clear").disabled=!reviewDraft.id;
  $("review-scope").replaceChildren(scopeContent(item));
  const annotations=marks().filter(a=>a.target===id);
  for(const mark of annotations)$("review-scope").append(element("p","muted",mark.feature+" · "+mark.severity+" · "+mark.status+": "+mark.comment));
  $("review-save-status").textContent="Private workflow only · canonical status stays unchanged";
}
function bindReviewQueue(){
  for(const [id,values] of [["feature",MARK_FEATURES],["severity",REVIEW_SEVERITY],["status",WORKFLOW_STATUS],["family",EXPERIMENT_FAMILY]]){
    populateOptions("queue-"+id,values,true);populateOptions("review-"+id,values);
  }
  for(const id of ["lane","feature","severity","status","family","archived"])$("queue-"+id).addEventListener("change",renderReviewQueue);
  $("review-queue").onclick=()=>run(()=>openReviewQueue());
  $("close-queue").onclick=()=>run(()=>{if(reviewDirty)throw new Error("Save or cancel the review edit first.");$("queue-dialog").close();});
  $("queue-dialog").addEventListener("cancel",e=>{if(reviewDirty){e.preventDefault();toast("Save or cancel the review edit first.");}});
  $("review-form").addEventListener("input",()=>{reviewDirty=true;$("review-save-status").textContent="Unsaved workflow edit";});
  $("review-form").onsubmit=e=>{
    e.preventDefault();run(async()=>{
      if(!reviewDraft)throw new Error("Choose artwork to review.");
      const record={...reviewDraft,workflow_status:$("review-status").value,feature:$("review-feature").value,
        severity:$("review-severity").value,family:$("review-family").value,candidate:$("review-candidate").checked,nomination_reason:$("review-reason").value};
      await mutate("review_save",{record});reviewDirty=false;editReview(record.target);renderReviewQueue();
      $("review-save-status").textContent="Saved privately · candidate nomination grants no canon approval";
    });
  };
  $("review-clear").onclick=()=>run(async()=>{
    if(!reviewDraft?.id)return;const target=reviewDraft.target;
    await mutate("review_delete",{id:reviewDraft.id});reviewDirty=false;editReview(target);renderReviewQueue();
  });
  $("review-cancel").onclick=()=>{reviewDirty=false;reviewDraft=null;$("review-form").hidden=true;};
  window.addEventListener("beforeunload",e=>{if(reviewDirty){e.preventDefault();e.returnValue="";}});
}
