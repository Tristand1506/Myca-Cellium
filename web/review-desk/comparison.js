"use strict";
let compareDraft=null, compareViews=[], compareObserver=null;
function defaultTransform(){return {zoom:1,pan:[0,0],alignment:{offset:[0,0],scale:1,rotation:0}};}
function compareSessions(){return state.workspace?.comparisons || [];}
function updateCompareSessions(){
  const select=$("compare-sessions"), chosen=select.value;
  select.replaceChildren();
  const placeholder=element("option","","Choose session"); placeholder.value=""; select.append(placeholder);
  for(const session of compareSessions()){const option=element("option","",session.name);option.value=session.id;select.append(option);}
  select.value=compareSessions().some(s=>s.id===chosen)?chosen:"";
}
function openAdvancedCompare(record=null){
  compareObserver?.disconnect();
  const ids=record?.items || [...selection];
  if(ids.length && (ids.length<2 || ids.length>4))throw new Error("Select two to four images or saved regions.");
  if(ids.some(id=>!findItem(id)))throw new Error("Comparison item is no longer available.");
  compareDraft=record?structuredClone(record):(ids.length?{name:"",items:ids,transforms:ids.map(defaultTransform),synchronized:false,mode:"side-by-side",opacity:.5,split:.5}:null);
  $("advanced-compare-controls").hidden=false; updateCompareSessions();
  $("compare-grid").replaceChildren(); compareViews=[];
  if(compareDraft) {
    $("compare-name").value=compareDraft.name; $("compare-mode").value=compareDraft.mode;
    $("compare-sync").checked=compareDraft.synchronized; $("compare-opacity").value=compareDraft.opacity; $("compare-split").value=compareDraft.split;
    buildComparison();
  } else {$("compare-status").textContent="Select a saved session and Restore, or select two to four items in the library."; }
  if(!$("comparison").open)$("comparison").showModal();
  applyComparison();
}
function numericControl(label,value,min,max,step,action){
  const node=element("label","",label), input=element("input");input.type="number";input.value=value;input.min=min;input.max=max;input.step=step;
  input.addEventListener("change",()=>run(()=>{const n=Number(input.value);if(!Number.isFinite(n)||n<min||n>max)throw new Error("Alignment value outside supported range.");action(n);applyComparison();}));
  node.append(input);return node;
}
function buildComparison(){
  $("compare-grid").replaceChildren(); compareViews=[];
  compareObserver?.disconnect();
  compareObserver=new ResizeObserver(()=>applyComparison());
  compareDraft.items.forEach((id,index)=>{
    const item=findItem(id), transform=compareDraft.transforms[index];
    const article=element("article","compare-pane"); article.dataset.index=index;
    article.append(element("p","eyebrow",identity(item)),element("h3","",item.title));
    const viewport=element("div","compare-viewport");viewport.tabIndex=0;viewport.setAttribute("aria-label","Zoom and pan "+item.title);
    const plane=element("div","compare-plane"), crop=element("div","compare-crop"), image=element("img");
    image.alt=item.title;image.draggable=false;image.src=item.asset.url;crop.append(image);plane.append(crop);viewport.append(plane);
    image.addEventListener("load",()=>applyComparison());
    let dragging=null;
    viewport.addEventListener("pointerdown",e=>{
      if(e.button!==0)return;dragging={x:e.clientX,y:e.clientY,pans:compareDraft.transforms.map(t=>[...t.pan])};
      viewport.setPointerCapture(e.pointerId);e.preventDefault();
    });
    viewport.addEventListener("pointermove",e=>{
      if(!dragging)return;
      const delta=[(e.clientX-dragging.x)/viewport.clientWidth,(e.clientY-dragging.y)/viewport.clientHeight];
      for(const i of compareDraft.synchronized?compareDraft.items.map((_,i)=>i):[index]){
        compareDraft.transforms[i].pan=dragging.pans[i].map((p,j)=>Math.max(-8,Math.min(8,p+delta[j])));
      }
      applyComparison();
    });
    for(const event of ["pointerup","pointercancel"])viewport.addEventListener(event,()=>{dragging=null;});
    viewport.addEventListener("wheel",e=>{e.preventDefault();zoomComparison(index,Math.exp(-e.deltaY*.002));},{passive:false});
    viewport.addEventListener("keydown",e=>{
      if(["+","=","-"].includes(e.key)){e.preventDefault();zoomComparison(index,e.key==="-"?.8:1.25);}
      else if(["ArrowLeft","ArrowRight","ArrowUp","ArrowDown"].includes(e.key)){
        e.preventDefault(); const delta=[e.key==="ArrowLeft"?-.05:e.key==="ArrowRight"?.05:0,e.key==="ArrowUp"?-.05:e.key==="ArrowDown"?.05:0];
        for(const i of compareDraft.synchronized?compareDraft.items.map((_,i)=>i):[index])compareDraft.transforms[i].pan=compareDraft.transforms[i].pan.map((p,j)=>Math.max(-8,Math.min(8,p+delta[j])));
        applyComparison();
      }
    });
    const tools=element("div","compare-pane-tools");
    const zoomLabel=element("span","compare-zoom-label");
    tools.append(button("−",()=>zoomComparison(index,.8)),zoomLabel,button("+",()=>zoomComparison(index,1.25)),button("Fit",()=>{compareDraft.transforms[index]=defaultTransform();buildComparison();applyComparison();}));
    const alignment=element("details","comparison-alignment");alignment.append(element("summary","","Manual alignment (view only)"));
    const controls=element("div","alignment-fields");
    for(const [label,key,min,max,step] of [["Offset X","x",-8,8,.01],["Offset Y","y",-8,8,.01],["Scale","scale",.1,10,.01],["Rotation °","rotation",-180,180,1]]){
      const value=key==="x"?transform.alignment.offset[0]:key==="y"?transform.alignment.offset[1]:transform.alignment[key];
      controls.append(numericControl(label,value,min,max,step,n=>{
        const t=compareDraft.transforms[index];
        if(key==="x"||key==="y")t.alignment.offset[key==="x"?0:1]=n;else t.alignment[key]=n;
      }));
    }
    alignment.append(controls);article.append(viewport,tools,alignment,scopeContent(item));
    $("compare-grid").append(article);compareViews.push({article,viewport,plane,crop,image,item,index,zoomLabel});
    compareObserver.observe(viewport);
  });
}
function zoomComparison(index,factor){
  for(const i of compareDraft.synchronized?compareDraft.items.map((_,i)=>i):[index])compareDraft.transforms[i].zoom=Math.max(.1,Math.min(16,compareDraft.transforms[i].zoom*factor));
  applyComparison();
}
function applyComparison(){
  if(!compareDraft)return;
  const layered=compareDraft.mode!=="side-by-side";
  $("compare-grid").classList.toggle("layered-comparison",layered);
  $("compare-grid").dataset.mode=compareDraft.mode;
  for(const pane of compareViews){
    const {image,item,viewport,plane,crop,index,zoomLabel}=pane;
    const w=image.naturalWidth,h=image.naturalHeight;if(!w||!h)continue;
    const r=item.detail?.rect || [0,0,1,1], cw=w*(r[2]-r[0]),ch=h*(r[3]-r[1]);
    const scale=Math.min(viewport.clientWidth/cw,viewport.clientHeight/ch);
    const fw=cw*scale,fh=ch*scale,t=compareDraft.transforms[index];
    plane.style.width=crop.style.width=fw+"px";plane.style.height=crop.style.height=fh+"px";
    plane.style.left=(viewport.clientWidth-fw)/2+"px";plane.style.top=(viewport.clientHeight-fh)/2+"px";
    plane.style.transform=`translate(${(t.pan[0]+t.alignment.offset[0])*viewport.clientWidth}px,${(t.pan[1]+t.alignment.offset[1])*viewport.clientHeight}px) rotate(${t.alignment.rotation}deg) scale(${t.zoom*t.alignment.scale})`;
    image.style.width=w*scale+"px";image.style.height=h*scale+"px";image.style.left=-r[0]*w*scale+"px";image.style.top=-r[1]*h*scale+"px";
    zoomLabel.textContent=Math.round(t.zoom*100)+"%";
    viewport.style.opacity=layered&&index===1&&compareDraft.mode==="overlay"?compareDraft.opacity:"1";
    viewport.style.clipPath=layered&&index===1&&compareDraft.mode==="slider"?`inset(0 ${(1-compareDraft.split)*100}% 0 0)`:"none";
    // A layered viewport cannot consume navigation belonging to its lower plane.
    viewport.style.pointerEvents=layered&&index===1?"none":"auto";
  }
  $("compare-opacity").disabled=compareDraft.mode!=="overlay";
  $("compare-split").disabled=compareDraft.mode!=="slider";
  $("compare-mode").querySelectorAll("option").forEach(o=>{o.disabled=o.value!=="side-by-side"&&compareDraft.items.length!==2;});
}
function bindComparisons(){
  $("saved-comparisons").onclick=()=>run(()=>openAdvancedCompare());
  $("compare-mode").onchange=()=>{if(!compareDraft)return;compareDraft.mode=$("compare-mode").value;applyComparison();};
  $("compare-sync").onchange=()=>{if(compareDraft)compareDraft.synchronized=$("compare-sync").checked;};
  for(const key of ["opacity","split"])$("compare-"+key).oninput=()=>{if(compareDraft){compareDraft[key]=Number($("compare-"+key).value);applyComparison();}};
  $("compare-reset").onclick=()=>{if(compareDraft){compareDraft.transforms=compareDraft.items.map(defaultTransform);buildComparison();applyComparison();}};
  $("compare-save").onclick=()=>run(async()=>{
    if(!compareDraft)throw new Error("Open a comparison first.");
    const record=structuredClone(compareDraft);record.name=$("compare-name").value.trim();
    if(!record.name)throw new Error("Give the private session a name.");
    await mutate("comparison_save",{record});
    compareDraft=structuredClone(compareSessions().find(s=>s.id===record.id)||compareSessions().at(-1));
    updateCompareSessions();$("compare-sessions").value=compareDraft.id;$("compare-status").textContent="Session saved privately · Undo available";
  });
  $("compare-restore").onclick=()=>run(()=>{
    const record=compareSessions().find(s=>s.id===$("compare-sessions").value);
    if(!record)throw new Error("Choose a saved session.");openAdvancedCompare(record);
  });
  $("compare-delete").onclick=()=>run(async()=>{
    const id=$("compare-sessions").value;if(!id)throw new Error("Choose a saved session.");
    await mutate("comparison_delete",{id});if(compareDraft?.id===id)delete compareDraft.id;
    updateCompareSessions();$("compare-status").textContent="Session deleted · Undo available";
  });
  $("comparison").addEventListener("close",()=>{compareObserver?.disconnect();});
}
