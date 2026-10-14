"use strict";
let iterationDraft=null,iterationFormDirty=false;
function iterations(){return state.workspace?.iterations||[];}
function iterationOrder(nodes){
  const done=new Set(),result=[];
  while(result.length<nodes.length){
    const ready=nodes.filter(n=>!done.has(n.id)&&n.parents.every(p=>done.has(p)));
    if(!ready.length)throw new Error("Invalid iteration cycle or parent reference.");
    for(const node of ready){done.add(node.id);result.push(node);}
  }
  return result;
}
function openHistory(sha=null){
  if(!$("history-dialog").open)$("history-dialog").showModal();
  renderIterations();editIteration(null,sha);
}
function renderIterations(){
  const graph=$("iteration-graph"), nodes=iterationOrder(iterations()), depths=new Map(), levels=[];
  for(const node of nodes){
    const depth=node.parents.length?1+Math.max(...node.parents.map(p=>depths.get(p))):0;
    depths.set(node.id,depth);(levels[depth]||=[]).push(node);
  }
  const canvas=element("div","iteration-canvas"), edges=svgNode("svg",{class:"iteration-edges","aria-hidden":"true"});
  const positions=new Map();let y=10;
  const defs=svgNode("defs"),marker=svgNode("marker",{id:"iteration-arrow",viewBox:"0 0 10 10",refX:9,refY:5,markerWidth:6,markerHeight:6,orient:"auto-start-reverse"});
  marker.append(svgNode("path",{d:"M0 0 L10 5 L0 10z",fill:"#b7d1b1"}));defs.append(marker);edges.append(defs);
  for(const level of levels){
    level.forEach((node,i)=>positions.set(node.id,{x:10+(i%4)*270,y:y+Math.floor(i/4)*190}));
    y+=Math.ceil(level.length/4)*190+30;
  }
  const width=Math.max(270,Math.min(4,Math.max(0,...levels.map(l=>l.length)))*270);
  canvas.style.width=width+"px";canvas.style.height=Math.max(100,y)+"px";
  edges.setAttribute("width",width);edges.setAttribute("height",Math.max(100,y));canvas.append(edges);
  for(const node of nodes){
    const pos=positions.get(node.id), item=findItem(node.asset_sha256),card=button("",()=>editIteration(node),"iteration-node");
    card.style.left=pos.x+"px";card.style.top=pos.y+"px";card.dataset.iteration=node.id;
    const image=element("img");image.src=item.asset.url;image.alt=item.title;
    card.append(image,element("strong","",node.title),element("small","",node.relationship+" · "+node.outcome),element("small","",node.features.join(", ")));
    if(isExperimental(item.asset))card.append(element("small","badge experiment","Experimental"));
    canvas.append(card);
    for(const parent of node.parents){
      const p=positions.get(parent),x1=p.x+120,y1=p.y+158,x2=pos.x+120,y2=pos.y;
      edges.append(svgNode("path",{d:`M${x1},${y1} C${x1},${y1+20} ${x2},${y2-20} ${x2},${y2}`,fill:"none",stroke:"#b7d1b1","stroke-width":1.5,"marker-end":"url(#iteration-arrow)"}));
    }
  }
  graph.replaceChildren(canvas);
  const list=element("ol");
  for(const node of nodes){
    const row=element("li");row.append(button(node.title+" · "+node.relationship+" · "+node.outcome,()=>editIteration(node)));
    if(node.parents.length)row.append(element("span","muted"," ← "+node.parents.map(p=>nodes.find(n=>n.id===p).title).join(", ")));
    list.append(row);
  }
  $("iteration-list").replaceChildren(list);
  if(!nodes.length)$("iteration-list").append(element("p","muted","No history recorded. Record a source, then link revisions or alternatives."));
}
function editIteration(node=null,sha=null){
  if(iterationFormDirty)throw new Error("Save the iteration or choose Record iteration again to discard the draft.");
  iterationDraft=node?structuredClone(node):{asset_sha256:sha||state.assets[0]?.sha256,title:"",relationship:"source",parents:[],features:[],corrections:"",prompt:"",outcome:"unreviewed"};
  const options=(select,values,selected)=>{
    select.replaceChildren(...values.map(([id,title])=>{const o=element("option","",title);o.value=id;o.selected=selected.includes(id);return o;}));
  };
  options($("iteration-asset"),state.assets.map(a=>[a.sha256,identity(findItem(a.sha256))+" · "+findItem(a.sha256).title]),[iterationDraft.asset_sha256]);
  options($("iteration-parents"),iterations().filter(n=>n.id!==iterationDraft.id).map(n=>[n.id,n.title]),iterationDraft.parents);
  options($("iteration-features"),MARK_FEATURES.map(f=>[f,f]),iterationDraft.features);
  for(const key of ["title","relationship","corrections","prompt","outcome"])$("iteration-"+key).value=iterationDraft[key];
  $("iteration-delete").disabled=!iterationDraft.id;
  $("iteration-status").textContent="Local record · no canon approval";showIterationScope();
}
function showIterationScope(){
  const item=findItem($("iteration-asset").value);
  $("iteration-scope").replaceChildren(...(item?[scopeContent(item)]:[]));
}
function bindIterations(){
  $("iteration-history").onclick=()=>run(()=>openHistory());
  $("close-history").onclick=()=>run(()=>{if(iterationFormDirty)throw new Error("Save the iteration or discard it with Record iteration before closing.");$("history-dialog").close();});
  $("history-dialog").addEventListener("cancel",e=>{if(iterationFormDirty){e.preventDefault();toast("Save the iteration or discard it with Record iteration.");}});
  $("new-iteration").onclick=()=>{iterationFormDirty=false;editIteration();};
  $("iteration-form").addEventListener("input",()=>{iterationFormDirty=true;$("iteration-status").textContent="Unsaved iteration";});
  $("iteration-asset").onchange=showIterationScope;
  $("iteration-form").onsubmit=e=>{
    e.preventDefault();run(async()=>{
      const record={...iterationDraft,asset_sha256:$("iteration-asset").value};
      for(const key of ["title","relationship","corrections","prompt","outcome"])record[key]=$("iteration-"+key).value;
      for(const key of ["parents","features"])record[key]=[...$("iteration-"+key).selectedOptions].map(o=>o.value);
      await mutate("iteration_save",{record});iterationFormDirty=false;
      editIteration(iterations().find(n=>n.id===record.id)||iterations().at(-1));renderIterations();
      $("iteration-status").textContent="Saved privately · Undo available";
    });
  };
  $("iteration-delete").onclick=()=>run(async()=>{
    if(!iterationDraft?.id)return;await mutate("iteration_delete",{id:iterationDraft.id});
    iterationFormDirty=false;editIteration();renderIterations();$("iteration-status").textContent="Deleted record · original unchanged · Undo available";
  });
  window.addEventListener("beforeunload",e=>{if(iterationFormDirty){e.preventDefault();e.returnValue="";}});
}
