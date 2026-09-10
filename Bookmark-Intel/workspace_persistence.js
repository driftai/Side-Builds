(function () {
'use strict';

const manager=document.querySelector('#workspace-manager');
const nameInput=document.querySelector('#workspace-name');
const savedSelect=document.querySelector('#workspace-saved');
const managerStatus=document.querySelector('#workspace-manager-status');
const managerLabel=document.querySelector('#workspace-current-label');
const dirtyLabel=document.querySelector('#workspace-dirty');
const importInput=document.querySelector('#workspace-import-file');
const refreshButton=document.querySelector('#workspace-refresh-all');
if(!manager||!window.BookmarkWorkspace)return;

const MAX_IMPORT_BYTES=26_000_000;
const MAX_IMPORT_SPACES=500;
const MAX_IMPORT_HISTORY=5;
let activeId=null;
let activeName='';
let dirty=false;
let suppressDirty=false;

const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const text=v=>String(v==null?'':v).trim();
const slug=v=>(text(v)||'bookmark-intel-workspace').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'').slice(0,80)||'bookmark-intel-workspace';

function setStatus(message){managerStatus.textContent=message||'';}
function markDirty(value=true){dirty=Boolean(value);const persisted=Boolean(activeId);dirtyLabel.textContent=persisted?(dirty?'unsaved changes':'saved'):'not saved';dirtyLabel.classList.toggle('saved',persisted&&!dirty);updateLabel();}
function updateLabel(){managerLabel.textContent=activeName||nameInput.value.trim()||'Unsaved workspace';}
function currentName(){return nameInput.value.trim()||activeName||'Bookmark Intel Workspace';}
function workspaceBusy(){return Boolean(document.querySelector('.pending-body,.space-refresh:disabled'));}
function ensureIdle(action){if(workspaceBusy())throw new Error(`Finish the current analysis/refresh before ${action}.`);}
function currentSpaceCount(){return window.BookmarkWorkspace.serializeWorkspace().spaces.length;}

async function jsonFetch(url,options){
  const response=await fetch(url,options);
  let payload={};
  try{payload=await response.json();}catch(_){payload={};}
  if(!response.ok)throw new Error(payload.detail||`Request failed (${response.status})`);
  return payload;
}

async function refreshSavedList(selectId=activeId){
  const payload=await jsonFetch('/api/workspaces');
  const rows=payload.workspaces||[];
  savedSelect.innerHTML='<option value="">Saved workspaces…</option>'+rows.map(row=>`<option value="${esc(row.id)}">${esc(row.name)} · ${Number(row.space_count)||0} spaces</option>`).join('');
  if(selectId&&rows.some(row=>row.id===selectId))savedSelect.value=selectId;
  return rows;
}

function graphSummary(graph){
  const stats=graph&&graph.stats||{};
  const lines=[`Clusters: ${stats.clusters||0}`,`Relationships: ${stats.relationships||0}`,`Corroborated facts: ${stats.agreements||0}`,`Disagreements: ${stats.conflicts||0}`];
  (graph&&graph.clusters||[]).forEach(cluster=>lines.push(`- ${cluster.label}: spaces ${(cluster.members||[]).map(m=>m.id).join(', ')}`));
  return lines;
}

function exportDocument(){
  const state=window.BookmarkWorkspace.serializeWorkspace();
  return {schema:'bookmark-intel-workspace',schema_version:1,id:activeId,name:currentName(),exported_at:new Date().toISOString(),state};
}

function markdownExport(doc){
  const lines=[`# ${doc.name}`,'',`Exported: ${doc.exported_at}`,'','## Workspace Intelligence','',...graphSummary(doc.state.relationship_snapshot),''];
  (doc.state.spaces||[]).forEach(space=>{
    lines.push(`## Space ${space.id} — ${space.payload?.data?.identity?.title||space.raw||'Result'}`,'',`Input: ${space.raw||''}`,'');
    if(space.last_change?.count){
      lines.push(`### Changes since previous capture (${space.last_change.count})`,'');
      space.last_change.changes.forEach(change=>lines.push(`- **${change.label}**: ${change.before||'∅'} → ${change.after||'∅'}`));
      lines.push('');
    }
    if(space.payload?.report)lines.push(space.payload.report,'');
    else if(space.error)lines.push(`Analysis error: ${space.error}`,'');
  });
  return lines.join('\n');
}

function htmlExport(doc){
  const graph=doc.state.relationship_snapshot||{};
  const sections=(doc.state.spaces||[]).map(space=>{
    const title=space.payload?.data?.identity?.title||space.raw||'Result';
    const changes=space.last_change?.count?`<details><summary>${space.last_change.count} changes since previous capture</summary><ul>${space.last_change.changes.map(c=>`<li><b>${esc(c.label)}</b>: ${esc(c.before||'∅')} → ${esc(c.after||'∅')}</li>`).join('')}</ul></details>`:'';
    const body=space.payload?.report?`<pre>${esc(space.payload.report)}</pre>`:`<p>${esc(space.error||'No completed result.')}</p>`;
    return `<details><summary>Space ${space.id} · ${esc(title)}</summary><div class="source">${esc(space.raw||'')}</div>${changes}${body}</details>`;
  }).join('');
  return `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(doc.name)}</title><style>body{max-width:1000px;margin:40px auto;padding:0 18px;background:#0c0e12;color:#eef1f6;font:15px/1.55 system-ui,sans-serif}h1{margin-bottom:4px}.muted,.source{color:#9099a8}.stats{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0}.stats span,details{border:1px solid #303746;background:#11151d;border-radius:12px;padding:10px 12px}details{margin:10px 0}summary{cursor:pointer;font-weight:700}pre{white-space:pre-wrap;overflow:auto;background:#090b0f;border-radius:10px;padding:14px;color:#d6dce6}.source{margin:8px 0;word-break:break-all}</style></head><body><h1>${esc(doc.name)}</h1><div class="muted">Bookmark Intel dossier · ${esc(doc.exported_at)}</div><div class="stats">${graphSummary(graph).slice(0,4).map(x=>`<span>${esc(x)}</span>`).join('')}</div>${sections}</body></html>`;
}

function download(content,type,extension){
  const blob=new Blob([content],{type});
  const objectUrl=URL.createObjectURL(blob);
  const anchor=document.createElement('a');
  anchor.href=objectUrl;anchor.download=`${slug(currentName())}.${extension}`;document.body.appendChild(anchor);anchor.click();anchor.remove();
  setTimeout(()=>URL.revokeObjectURL(objectUrl),0);
}

function validateImportState(doc){
  if(doc?.schema!=='bookmark-intel-workspace'||Number(doc?.schema_version)!==1||!doc?.state||!Array.isArray(doc.state.spaces))throw new Error('That file is not a supported Bookmark Intel workspace export.');
  const importedName=text(doc.name);
  if(importedName.length>120||/[\u0000-\u001f\u007f]/.test(importedName))throw new Error('Workspace import contains an invalid workspace name.');
  if(doc.state.spaces.length>MAX_IMPORT_SPACES)throw new Error(`Workspace import exceeds the ${MAX_IMPORT_SPACES}-space limit.`);
  const ids=new Set();
  doc.state.spaces.forEach(space=>{
    const id=Number(space?.id);
    if(!Number.isInteger(id)||id<1||ids.has(id))throw new Error('Workspace import contains invalid or duplicate space ids.');
    ids.add(id);
    if(!['complete','failed'].includes(space.status))throw new Error('Workspace import contains a transient/unsupported space state.');
    if(!Array.isArray(space.history||[])||(space.history||[]).length>MAX_IMPORT_HISTORY)throw new Error('Workspace import contains invalid or excessive refresh history.');
    if(space.status==='complete'&&(!space.payload||typeof space.payload!=='object'||!space.payload.data||typeof space.payload.data!=='object'||typeof space.payload.report!=='string'))throw new Error('Workspace import contains a malformed completed result payload.');
  });
  const nextId=Number(doc.state.next_space_id||1);
  if(!Number.isInteger(nextId)||nextId<1||(ids.size&&nextId<=Math.max(...ids)))throw new Error('Workspace import contains an invalid next space id.');
  return doc;
}

async function saveWorkspace(){
  ensureIdle('saving');
  const name=currentName();setStatus('Saving…');
  const payload=await jsonFetch('/api/workspaces',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({id:activeId,name,state:window.BookmarkWorkspace.serializeWorkspace()})});
  activeId=payload.id;activeName=payload.name;nameInput.value=payload.name;markDirty(false);await refreshSavedList(activeId);setStatus(`Saved ${payload.name}.`);
}

async function loadWorkspace(id){
  if(!id)return;
  ensureIdle('loading another workspace');
  if(dirty&&currentSpaceCount()>0&&!window.confirm('Load the saved workspace and replace the current unsaved view?'))return;
  setStatus('Loading…');
  const payload=await jsonFetch(`/api/workspaces/${encodeURIComponent(id)}`);
  suppressDirty=true;
  try{window.BookmarkWorkspace.restoreWorkspace(payload.state);}finally{suppressDirty=false;}
  activeId=payload.id;activeName=payload.name;nameInput.value=payload.name;markDirty(false);savedSelect.value=payload.id;setStatus(`Loaded ${payload.name} without re-running analysis.`);
}

async function deleteWorkspace(){
  const id=savedSelect.value||activeId;if(!id)return setStatus('Choose a saved workspace first.');
  const label=savedSelect.options[savedSelect.selectedIndex]?.textContent||'this workspace';
  if(!window.confirm(`Delete saved ${label}? The currently open results will stay on screen.`))return;
  await jsonFetch(`/api/workspaces/${encodeURIComponent(id)}`,{method:'DELETE'});
  if(id===activeId){activeId=null;activeName='';markDirty(true);}
  await refreshSavedList();setStatus('Saved workspace deleted.');
}

async function importJson(file){
  ensureIdle('importing a workspace');
  if(!file)return;
  if(file.size>MAX_IMPORT_BYTES)throw new Error('Workspace import exceeds the 26 MB client limit.');
  const raw=await file.text();
  const doc=validateImportState(JSON.parse(raw));
  if(dirty&&currentSpaceCount()>0&&!window.confirm('Import this workspace and replace the current unsaved view?'))return;
  suppressDirty=true;
  try{window.BookmarkWorkspace.restoreWorkspace(doc.state);}finally{suppressDirty=false;}
  activeId=null;activeName=text(doc.name)||'Imported workspace';nameInput.value=activeName;markDirty(true);savedSelect.value='';setStatus(`Imported ${activeName}. Save it to keep it in the local workspace library.`);
}

async function refreshAll(){
  ensureIdle('refreshing');
  refreshButton.disabled=true;setStatus('Refreshing completed spaces…');
  try{
    const result=await window.BookmarkWorkspace.refreshAll();
    const changed=result.results.filter(r=>r.ok&&r.change?.count>0);
    const totalChanges=changed.reduce((sum,r)=>sum+(r.change?.count||0),0);
    setStatus(`Refresh complete: ${result.ok}/${result.total} succeeded · ${changed.length} changed space${changed.length===1?'':'s'} · ${totalChanges} detected change${totalChanges===1?'':'s'}.`);
  }finally{refreshButton.disabled=false;}
}

function guardedExport(format){
  ensureIdle('exporting');
  const doc=exportDocument();
  if(format==='json')return download(JSON.stringify(doc,null,2),'application/json','json');
  if(format==='md')return download(markdownExport(doc),'text/markdown;charset=utf-8','md');
  return download(htmlExport(doc),'text/html;charset=utf-8','html');
}

document.querySelector('#workspace-save').addEventListener('click',()=>saveWorkspace().catch(e=>setStatus(e.message)));
document.querySelector('#workspace-load').addEventListener('click',()=>loadWorkspace(savedSelect.value).catch(e=>setStatus(e.message)));
document.querySelector('#workspace-new').addEventListener('click',()=>{activeId=null;activeName='';nameInput.value='';savedSelect.value='';markDirty(true);setStatus('Current results will be saved as a new workspace the next time you press Save.');});
document.querySelector('#workspace-delete').addEventListener('click',()=>deleteWorkspace().catch(e=>setStatus(e.message)));
refreshButton.addEventListener('click',()=>refreshAll().catch(e=>setStatus(e.message)));
document.querySelector('#workspace-export-json').addEventListener('click',()=>{try{guardedExport('json');}catch(e){setStatus(e.message);}});
document.querySelector('#workspace-export-md').addEventListener('click',()=>{try{guardedExport('md');}catch(e){setStatus(e.message);}});
document.querySelector('#workspace-export-html').addEventListener('click',()=>{try{guardedExport('html');}catch(e){setStatus(e.message);}});
document.querySelector('#workspace-import').addEventListener('click',()=>{try{ensureIdle('importing');importInput.click();}catch(e){setStatus(e.message);}});
importInput.addEventListener('change',()=>{const file=importInput.files&&importInput.files[0];importJson(file).catch(e=>setStatus(e.message)).finally(()=>{importInput.value='';});});
nameInput.addEventListener('input',()=>{activeName=nameInput.value.trim();markDirty(true);});
savedSelect.addEventListener('change',()=>setStatus(savedSelect.value?'Ready to load selected workspace.':''));
document.addEventListener('bookmark-workspace-updated',()=>{if(!suppressDirty)markDirty(true);});

refreshSavedList().catch(e=>setStatus(`Saved workspace list unavailable: ${e.message}`));
updateLabel();markDirty(false);
window.BookmarkPersistence={exportDocument,markdownExport,htmlExport,refreshSavedList,validateImportState};
})();