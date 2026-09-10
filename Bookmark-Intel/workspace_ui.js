(function () {
'use strict';

const esc = s => String(s ?? '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const safeHref = u => { const s=String(u??'').trim(); return /^https?:\/\//i.test(s) ? esc(s) : '#'; };
const val = v => Array.isArray(v) ? v.map(x => x && typeof x === 'object' ? JSON.stringify(x) : String(x)).join(', ') : (v && typeof v === 'object' ? JSON.stringify(v) : String(v ?? ''));

const form=document.querySelector('#form');
const url=document.querySelector('#url');
const go=document.querySelector('#go');
const status=document.querySelector('#status');
const spaces=document.querySelector('#spaces');
const empty=document.querySelector('#empty');
const count=document.querySelector('#workspace-count');
const intel=document.querySelector('#workspace-intel');
const intelContent=document.querySelector('#workspace-intel-content');
const MAX_PARALLEL=3;
const MAX_HISTORY=5;
let nextSpaceId=1;
const workspaceState=new Map();

function stripBulletPrefix(s){return String(s??'').replace(/^\s*(?:(?:[-*•]+)|(?:\d+[.)]))\s*/,'').trim();}
function cleanUrlToken(token){let s=String(token??'').trim();while(/[.,;]$/.test(s))s=s.slice(0,-1);while(s.endsWith(')')&&((s.match(/\(/g)||[]).length<(s.match(/\)/g)||[]).length))s=s.slice(0,-1);while(s.endsWith(']')&&((s.match(/\[/g)||[]).length<(s.match(/\]/g)||[]).length))s=s.slice(0,-1);return s;}
function parseTargets(raw){const text=String(raw??'').replace(/\r\n?/g,'\n').trim();if(!text)return[];const targets=[],seen=new Set();const add=value=>{const v=String(value??'').trim();if(!v||seen.has(v))return;seen.add(v);targets.push(v);};const tokenRe=/https?:\/\/[^\s<>"']+|\[([^\[\]\r\n]+)\]/gi;for(const sourceLine of text.split('\n')){const line=stripBulletPrefix(sourceLine);if(!line)continue;const normalized=line.replace(/([),;\]])(?=https?:\/\/)/gi,'$1 ');const explicit=[];tokenRe.lastIndex=0;let match;while((match=tokenRe.exec(normalized))!==null){const whole=match[0];if(/^https?:\/\//i.test(whole)){const cleaned=cleanUrlToken(whole);if(cleaned)explicit.push({index:match.index,value:cleaned});continue;}const term=String(match[1]??'').trim();if(!term)continue;const after=normalized.slice(tokenRe.lastIndex);if(/^\s*\(\s*https?:\/\//i.test(after))continue;explicit.push({index:match.index,value:term});}if(explicit.length){explicit.sort((a,b)=>a.index-b.index).forEach(item=>add(item.value));}else{add(line);}}return targets;}

function spaceTitle(payload,fallback){const d=payload?.data||{},i=d.identity||{};return i.title||d.fetch?.final_url||d.input?.url||d.input?.raw||fallback;}
function spaceSource(payload,fallback){const d=payload?.data||{};return d.input?.raw||d.input?.url||d.fetch?.final_url||fallback;}

function renderSearchResearch(sr){
  if(!sr||!sr.query)return'';
  const sources=sr.sources||[],compiled=sr.compiled_facts||[];
  return `<div class="card wide"><div class="label">Search research plan</div><div class="value">${esc(sr.query)}</div><div class="muted">${esc(sr.organic_selected??0)}/5 organic · Wikipedia ${sr.wikipedia_selected?'selected':'attempted / unavailable'} · Fandom ${sr.fandom_selected?'selected':'attempted / unavailable'} · ${esc(sr.sources_succeeded??0)}/${esc(sr.sources_selected??0)} source analyses succeeded</div>${sr.dominant_source_kind?`<div class="muted">dominant analyzed source type: ${esc(sr.dominant_source_kind)}</div>`:''}</div>${sources.length?`<div class="card wide"><div class="label">Analyzed search sources</div>${sources.map((s,idx)=>{const a=s.analysis||{},facts=a.key_facts||[];return `<div class="source-row"><div class="source-head"><span class="source-role">${esc(s.role||'source')}</span><b>${idx+1}. <a href="${safeHref(s.url)}" target="_blank" rel="noreferrer noopener">${esc(a.title||s.title||s.url)}</a></b><span class="muted">${esc(s.status||'unknown')}</span></div>${a.kind?`<div class="muted">${esc(a.kind)} · extraction ${Math.round((Number(a.quality_score)||0)*100)}%</div>`:''}${a.summary?`<div class="summary">${esc(a.summary)}</div>`:''}${facts.length?`<div class="source-facts">${facts.slice(0,8).map(f=>`<b>${esc(f.label)}</b>: ${esc(f.value)}`).join(' · ')}</div>`:''}${s.error?`<div class="muted">${esc(s.error)}</div>`:''}</div>`}).join('')}</div>`:''}${compiled.length?`<div class="card wide"><div class="label">Compiled facts across sources</div>${compiled.slice(0,30).map(f=>`<div class="compiled-row"><b>${esc(f.label)}</b><div class="muted">${(f.values||[]).slice(0,5).map(v=>`${esc(v.value)} (${esc(v.source_count)} source${Number(v.source_count)===1?'':'s'})`).join(' · ')}</div></div>`).join('')}</div>`:''}`;
}

function renderResult(p){
  const d=p.data,c=d.classification||{},i=d.identity||{},b=d.bookmark||{},q=d.quality||{},a=d.acquisition||{},facts=d.key_facts||[],entities=d.entities||[],sections=d.sections||{},links=(d.links||{}).important||[],attempts=a.attempts||[],prov=d.provider_enrichment||{},archive=d.evidence_archive||{},astats=archive.capture_stats||{},afacts=archive.labeled_facts||[],alinks=archive.links||[],sr=d.search_research||{};
  return `<div class="grid">
<div class="card"><div class="label">Type</div><div class="value">${esc(c.kind)}</div><div class="muted">classification confidence ${Math.round((c.confidence||0)*100)}%</div></div>
<div class="card"><div class="label">Extraction quality</div><div class="confidence">${Math.round((q.extraction_score||0)*100)}%</div><div class="muted">${esc(q.extraction_grade||'legacy / not scored')}</div></div>
<div class="card wide"><div class="label">Title / Query</div><div class="value">${esc(i.title||d.fetch?.final_url||d.input?.url||d.input?.raw)}</div></div>
<div class="card"><div class="label">Category</div><div class="value">${esc(c.category)}</div></div><div class="card"><div class="label">Suggested folder</div><div class="value">${esc(b.suggested_folder)}</div></div>
<div class="card"><div class="label">Acquisition</div><div class="value">${esc(a.method||'legacy')}</div><div class="muted">${a.rendered?'browser rendering used somewhere in discovery':'browser rendering not required'}</div></div><div class="card"><div class="label">Acquisition / search-page score</div><div class="value">${esc(a.acquisition_score??'—')}</div><div class="attempts">${attempts.map(x=>`${esc(x.method)}: ${x.ok?'ok':'failed'}`).join(' → ')}</div></div>
${prov.matched?`<div class="card"><div class="label">Provider enrichment</div><div class="value">${esc(prov.adapter)}</div><div class="muted">${prov.sufficient?'authoritative structured data used':'partial structured data'}</div></div>`:''}
<div class="card wide"><div class="label">Summary / recovered description</div><p class="summary">${esc(d.summary)}</p></div>${renderSearchResearch(sr)}
<div class="card wide"><div class="label">Tags</div><div class="chips">${(d.tags||[]).map(x=>`<span class="chip">${esc(x)}</span>`).join('')}</div></div>
${facts.length?`<div class="card"><div class="label">Key facts</div><ul class="list">${facts.map(x=>`<li><b>${esc(x.label)}</b>: ${esc(x.value)}</li>`).join('')}</ul></div>`:''}${entities.length?`<div class="card"><div class="label">Entities</div><ul class="list">${entities.map(x=>`<li>${esc(x.type)} — ${esc(x.name)}</li>`).join('')}</ul></div>`:''}
${Object.keys(sections).length?`<div class="card wide"><div class="label">Dynamic sections</div>${Object.entries(sections).map(([name,obj])=>`<h3>${esc(name)}</h3><ul class="list">${Object.entries(obj).map(([k,v])=>`<li><b>${esc(k)}</b>: ${esc(val(v))}</li>`).join('')}</ul>`).join('')}</div>`:''}
${links.length?`<div class="card wide"><div class="label">Selected / important links</div><ul class="list">${links.map(x=>`<li><a href="${safeHref(x.url)}" target="_blank" rel="noreferrer noopener">${esc(x.label)}</a> — ${esc(x.relationship)}</li>`).join('')}</ul></div>`:''}
${Object.keys(archive).length?`<div class="card wide archive"><div class="label">Evidence archive · retained source details</div><p class="muted">${esc(archive.capture_note||'Useful source evidence that was not necessarily promoted into the curated summary.')}</p><div class="archive-grid"><div class="archive-stat"><b>${esc(astats.labeled_facts_retained??afacts.length)}</b><div class="muted">labeled facts</div></div><div class="archive-stat"><b>${esc(astats.links_retained??alinks.length)}</b><div class="muted">links retained</div></div><div class="archive-stat"><b>${esc(astats.metadata_entries_retained??(archive.metadata||[]).length)}</b><div class="muted">metadata entries</div></div></div>${afacts.length?`<details><summary>Archived labeled facts</summary><ul class="list">${afacts.slice(0,60).map(x=>`<li><b>${esc(x.label)}</b>: ${esc(x.value)} <span class="muted">(${esc(x.source)})</span></li>`).join('')}${afacts.length>60?`<li>… ${afacts.length-60} more in Raw JSON</li>`:''}</ul></details>`:''}${alinks.length?`<details><summary>All discovered links</summary><ul class="list archive-links">${alinks.slice(0,100).map(x=>`<li><a href="${safeHref(x.url)}" target="_blank" rel="noreferrer noopener">${esc(x.label)}</a> — ${esc(x.relationship)} / ${esc(x.region)}${x.selected_for_research?' · selected':''}</li>`).join('')}${alinks.length>100?`<li>… ${alinks.length-100} more in Raw JSON</li>`:''}</ul></details>`:''}</div>`:''}
<div class="card wide"><div class="label">Why this bookmark might matter</div><p class="summary">${esc(b.why_it_might_matter)}</p></div>
<div class="card wide"><div class="tabs"><button class="active" data-tab="report">Readable report</button><button data-tab="json">Raw JSON</button></div><pre class="report-view">${esc(p.report)}</pre><pre class="json-view hidden">${esc(JSON.stringify(d,null,2))}</pre></div></div>`;
}

function renderChangeSummary(changeSet){
  if(!changeSet||!Number(changeSet.count))return'';
  const changes=changeSet.changes||[];
  return `<details class="change-card"><summary>${esc(changeSet.count)} change${Number(changeSet.count)===1?'':'s'} since previous capture</summary><div class="change-list">${changes.map(change=>`<div class="change-row"><span class="change-type">${esc(change.type)}</span><b>${esc(change.label)}</b><div class="intel-meta">${esc(change.before||'∅')} → ${esc(change.after||'∅')}</div></div>`).join('')}${changeSet.truncated?'<div class="intel-meta">Additional changes were omitted from this compact view.</div>':''}</div></details>`;
}

const relationNames={duplicate_resource:'Duplicate / canonical resource',same_subject:'Same subject',derived_source:'Search ↔ source',references:'Direct reference',related_subject:'Related subject'};
function spaceButton(id,title){return `<button type="button" class="intel-space" data-space-target="${id}">Space ${id} · ${esc(title)}</button>`;}
function renderAgreements(rows){if(!rows?.length)return'';return `<div class="intel-section"><div class="intel-subtitle">Corroborated facts</div>${rows.map(x=>`<div class="intel-row agreement"><b>${esc(x.displayLabel)}</b>: ${esc(x.value)} <span class="intel-meta">${esc(x.support)} supporting source${Number(x.support)===1?'':'s'} · spaces ${x.spaces.map(esc).join(', ')}</span></div>`).join('')}</div>`;}
function renderConflicts(rows){if(!rows?.length)return'';return `<div class="intel-section"><div class="intel-subtitle">Disagreements / variants</div>${rows.map(x=>`<div class="intel-row conflict"><b>${esc(x.displayLabel)}</b>${x.values.map(v=>`<div>${esc(v.value)} <span class="intel-meta">${esc(v.support)} support · spaces ${v.spaces.map(esc).join(', ')}</span></div>`).join('')}</div>`).join('')}</div>`;}
function renderCluster(cluster){const top=cluster.sourceRanking?.[0];return `<article class="cluster-card"><div class="cluster-head"><div><div class="label">Subject cluster</div><h3>${esc(cluster.label)}</h3></div><button type="button" class="ghost mini" data-cluster-focus="${cluster.members.map(m=>m.id).join(',')}">Focus spaces</button></div><div class="cluster-members">${cluster.members.map(m=>spaceButton(m.id,m.title)).join('')}</div>${top?`<div class="intel-best"><b>Best current source:</b> Space ${esc(top.id)} · ${esc(top.title)} <span class="intel-meta">source confidence ${Math.round((top.score||0)*100)}% · extraction ${Math.round((top.quality||0)*100)}%</span></div>`:''}${cluster.overview?`<p class="intel-overview">${esc(cluster.overview)}</p>`:''}${renderAgreements(cluster.agreements)}${renderConflicts(cluster.conflicts)}${cluster.sourceRanking?.length>1?`<div class="intel-section"><div class="intel-subtitle">Source ranking</div>${cluster.sourceRanking.slice(0,5).map((s,i)=>`<div class="intel-row">${i+1}. Space ${esc(s.id)} · ${esc(s.title)} <span class="intel-meta">${Math.round((s.score||0)*100)}% source confidence · ${esc(s.kind)}</span></div>`).join('')}</div>`:''}${cluster.relationships?.length?`<details class="intel-evidence"><summary>Relationship evidence</summary>${cluster.relationships.map(r=>`<div class="intel-row"><b>${esc(relationNames[r.type]||r.type)}</b> · Space ${esc(r.a)} ↔ ${esc(r.b)} <span class="intel-meta">${Math.round((r.confidence||0)*100)}%</span><div class="intel-meta">${(r.reasons||[]).map(esc).join(' · ')}</div></div>`).join('')}</details>`:''}</article>`;}
function renderWarnings(rows){if(!rows?.length)return'';return `<article class="intel-warning"><div class="intel-subtitle">Search-source quality warnings</div><p class="intel-meta">These stay in the original search evidence, but are flagged as weak subject matches so they should not silently strengthen a dossier.</p>${rows.slice(0,12).map(w=>`<div class="intel-row"><b>Space ${esc(w.spaceId)} · ${esc(w.sourceTitle)}</b><div class="intel-meta">${esc(w.role)} · relevance ${Math.round((w.relevance||0)*100)}% · query match ${Math.round((w.queryMatch||0)*100)}%${w.url?` · ${esc(w.url)}`:''}</div></div>`).join('')}</article>`;}

function wireIntelActions(){
  intelContent.querySelectorAll('[data-space-target]').forEach(btn=>btn.addEventListener('click',()=>{const node=spaces.querySelector(`.space[data-space-id="${btn.dataset.spaceTarget}"]`);if(node){node.open=true;node.scrollIntoView({behavior:'smooth',block:'start'});}}));
  intelContent.querySelectorAll('[data-cluster-focus]').forEach(btn=>btn.addEventListener('click',()=>{const ids=new Set(btn.dataset.clusterFocus.split(','));spaces.querySelectorAll(':scope > .space').forEach(node=>node.open=ids.has(node.dataset.spaceId));const first=spaces.querySelector(`.space[data-space-id="${[...ids][0]}"]`);if(first)first.scrollIntoView({behavior:'smooth',block:'start'});}));
}

function getRelationshipGraph(){
  const complete=[...workspaceState.values()].filter(x=>x.status==='complete'&&x.payload);
  if(complete.length<2||!window.BookmarkRelationships)return {nodes:[],edges:[],clusters:[],looseEdges:[],standalone:complete.map(x=>x.id),searchWarnings:[],stats:{spaces:complete.length,clusters:0,agreements:0,conflicts:0,relationships:0}};
  return window.BookmarkRelationships.analyzeWorkspace(complete);
}

function renderWorkspaceIntel(){
  const complete=[...workspaceState.values()].filter(x=>x.status==='complete');
  if(complete.length<2||!window.BookmarkRelationships){intel.classList.add('hidden');intelContent.replaceChildren();return;}
  const graph=getRelationshipGraph();
  const s=graph.stats||{};
  const stats=`<div class="intel-stats"><div><b>${esc(s.clusters||0)}</b><span>clusters</span></div><div><b>${esc(s.relationships||0)}</b><span>relationships</span></div><div><b>${esc(s.agreements||0)}</b><span>corroborated facts</span></div><div><b>${esc(s.conflicts||0)}</b><span>disagreements</span></div></div>`;
  const clusters=graph.clusters?.length?graph.clusters.map(renderCluster).join(''):`<div class="intel-empty">No strong same-subject cluster yet. Bookmark Intel is deliberately keeping these completed spaces separate rather than guessing.</div>`;
  const loose=graph.looseEdges?.length?`<details class="intel-loose"><summary>Other explicit relationships (${graph.looseEdges.length})</summary>${graph.looseEdges.slice(0,12).map(r=>`<div class="intel-row"><b>${esc(relationNames[r.type]||r.type)}</b> · Space ${esc(r.a)} ↔ ${esc(r.b)} <span class="intel-meta">${Math.round((r.confidence||0)*100)}% · ${(r.reasons||[]).map(esc).join(' · ')}</span></div>`).join('')}</details>`:'';
  intelContent.innerHTML=stats+renderWarnings(graph.searchWarnings)+clusters+loose;
  intel.classList.remove('hidden');
  wireIntelActions();
}

function emitWorkspaceUpdated(){document.dispatchEvent(new CustomEvent('bookmark-workspace-updated',{detail:{spaces:workspaceState.size}}));}
function updateWorkspace(){const n=spaces.querySelectorAll(':scope > .space').length;count.textContent=`${n} space${n===1?'':'s'}`;empty.classList.toggle('hidden',n>0);renderWorkspaceIntel();emitWorkspaceUpdated();}
function removeSpace(space){workspaceState.delete(Number(space.dataset.spaceId));space.remove();updateWorkspace();}
function wireRemove(space){space.querySelector('.space-remove').addEventListener('click',e=>{e.preventDefault();e.stopPropagation();removeSpace(space);});}
function wireSpace(space){wireRemove(space);const refresh=space.querySelector('.space-refresh');if(refresh)refresh.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();refreshSpaceById(Number(space.dataset.spaceId)).then(result=>{status.textContent=result.ok?(result.change?.count?`Space ${result.id} refreshed · ${result.change.count} change${result.change.count===1?'':'s'} detected.`:`Space ${result.id} refreshed · no meaningful changes.`):`Space ${result.id} refresh failed: ${result.error}`;});});space.querySelectorAll('[data-tab]').forEach(btn=>btn.addEventListener('click',()=>{space.querySelectorAll('[data-tab]').forEach(b=>b.classList.remove('active'));btn.classList.add('active');space.querySelector('.report-view').classList.toggle('hidden',btn.dataset.tab!=='report');space.querySelector('.json-view').classList.toggle('hidden',btn.dataset.tab!=='json');}));}

function createPendingSpace(raw){const id=nextSpaceId++;const space=document.createElement('details');space.className='space';space.dataset.spaceId=String(id);workspaceState.set(id,{id,raw,status:'pending',payload:null,history:[],last_change:null});space.innerHTML=`<summary class="space-summary"><span class="space-index">${id}</span><div class="space-heading"><div class="space-title">Analyzing…</div><div class="space-source">${esc(raw)}</div></div><div class="space-badges"><span class="space-badge">queued</span></div><button class="space-remove" type="button" aria-label="Remove result space">Remove</button></summary><div class="space-body pending-body">Waiting for the normal Bookmark Intel analysis pipeline…</div>`;spaces.appendChild(space);wireRemove(space);updateWorkspace();return space;}
function markWorking(space){const state=workspaceState.get(Number(space.dataset.spaceId));if(state)state.status='working';const badge=space.querySelector('.space-badge'),body=space.querySelector('.pending-body');if(badge)badge.textContent='working';if(body)body.textContent='Running the normal Bookmark Intel analysis pipeline…';}
function completeSpace(space,payload,raw,meta={}){const id=Number(space.dataset.spaceId),d=payload.data||{},c=d.classification||{},q=d.quality||{},prior=workspaceState.get(id)||{};const history=Array.isArray(meta.history)?meta.history:(prior.history||[]);const lastChange=meta.lastChange!==undefined?meta.lastChange:(prior.last_change||null);const refreshedAt=meta.refreshedAt!==undefined?meta.refreshedAt:(prior.refreshed_at||null);workspaceState.set(id,{id,raw,status:'complete',payload,history,last_change:lastChange,refreshed_at:refreshedAt});space.innerHTML=`<summary class="space-summary"><span class="space-index">${esc(id)}</span><div class="space-heading"><div class="space-title">${esc(spaceTitle(payload,raw))}</div><div class="space-source">${esc(spaceSource(payload,raw))}</div></div><div class="space-badges"><span class="space-badge">${esc(c.kind||'result')}</span><span class="space-badge">${Math.round((q.extraction_score||0)*100)}%</span>${lastChange?.count?`<span class="space-badge changed">${esc(lastChange.count)} changed</span>`:''}</div><button class="space-refresh" type="button" aria-label="Refresh this result space">Refresh</button><button class="space-remove" type="button" aria-label="Remove result space">Remove</button></summary><div class="space-body">${renderChangeSummary(lastChange)}${renderResult(payload)}</div>`;space.open=false;wireSpace(space);if(!meta.suppressUpdate)updateWorkspace();}
function failSpace(space,raw,message,meta={}){const id=Number(space.dataset.spaceId);workspaceState.set(id,{id,raw,status:'failed',payload:null,error:String(message||'Analysis failed'),history:meta.history||[]});space.innerHTML=`<summary class="space-summary"><span class="space-index">${esc(id)}</span><div class="space-heading"><div class="space-title">Analysis failed</div><div class="space-source">${esc(raw)}</div></div><div class="space-badges"><span class="space-badge">error</span></div><button class="space-remove" type="button" aria-label="Remove result space">Remove</button></summary><div class="space-body error-body">${esc(message)}</div>`;space.open=false;wireRemove(space);if(!meta.suppressUpdate)updateWorkspace();}

async function requestAnalysis(raw){const r=await fetch('/api/analyze',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({url:raw})});const payload=await r.json();if(!r.ok)throw new Error(payload.detail||'Analysis failed');return payload;}
async function analyzeJob(job,state){markWorking(job.space);try{const payload=await requestAnalysis(job.raw);completeSpace(job.space,payload,job.raw);state.ok++;}catch(err){failSpace(job.space,job.raw,err.message);state.failed++;}finally{state.done++;status.textContent=`Processing ${state.done}/${state.total} · ${state.ok} completed${state.failed?` · ${state.failed} failed`:''}`;updateWorkspace();}}
async function runBatch(targets){const jobs=targets.map(raw=>({raw,space:createPendingSpace(raw)}));const state={total:jobs.length,done:0,ok:0,failed:0};let cursor=0;async function worker(){while(true){const index=cursor++;if(index>=jobs.length)return;await analyzeJob(jobs[index],state);}}const workers=Array.from({length:Math.min(MAX_PARALLEL,jobs.length)},()=>worker());await Promise.all(workers);return state;}

async function refreshSpaceById(id){
  const state=workspaceState.get(Number(id));
  if(!state||state.status!=='complete'||!state.payload)return {id:Number(id),ok:false,error:'No completed capture is available to refresh.'};
  const space=spaces.querySelector(`.space[data-space-id="${Number(id)}"]`),button=space&&space.querySelector('.space-refresh');
  if(button){button.disabled=true;button.textContent='Refreshing…';}
  try{
    const payload=await requestAnalysis(state.raw);
    const change=window.BookmarkChanges?window.BookmarkChanges.comparePayloads(state.payload,payload):{checked_at:new Date().toISOString(),count:0,changes:[]};
    const history=[...(state.history||[]),{captured_at:new Date().toISOString(),payload:state.payload}].slice(-MAX_HISTORY);
    completeSpace(space,payload,state.raw,{history,lastChange:change,refreshedAt:new Date().toISOString()});
    return {id:Number(id),ok:true,change};
  }catch(err){
    if(button){button.disabled=false;button.textContent='Refresh';}
    return {id:Number(id),ok:false,error:String(err.message||err)};
  }
}

async function refreshAll(){
  const ids=[...workspaceState.values()].filter(x=>x.status==='complete'&&x.payload).map(x=>x.id);
  const results=[];let cursor=0;
  async function worker(){while(true){const index=cursor++;if(index>=ids.length)return;results[index]=await refreshSpaceById(ids[index]);}}
  const workers=Array.from({length:Math.min(MAX_PARALLEL,ids.length)},()=>worker());
  await Promise.all(workers);
  return {total:ids.length,ok:results.filter(x=>x&&x.ok).length,failed:results.filter(x=>x&&!x.ok).length,results};
}

function serializableState(state){return {id:state.id,raw:state.raw,status:state.status,payload:state.payload||null,error:state.error||null,history:state.history||[],last_change:state.last_change||null,refreshed_at:state.refreshed_at||null};}
function serializeWorkspace(){const saved=[...workspaceState.values()].filter(x=>x.status==='complete'||x.status==='failed').map(serializableState);return {schema_version:1,next_space_id:nextSpaceId,saved_at:new Date().toISOString(),spaces:saved,relationship_snapshot:getRelationshipGraph(),transient_spaces_omitted:workspaceState.size-saved.length};}
function restoreWorkspace(snapshot){
  if(!snapshot||!Array.isArray(snapshot.spaces))throw new Error('Workspace snapshot is missing its spaces array.');
  workspaceState.clear();spaces.replaceChildren();let maxId=0;
  snapshot.spaces.forEach(saved=>{
    const id=Number(saved.id);if(!Number.isInteger(id)||id<1)return;maxId=Math.max(maxId,id);
    const space=document.createElement('details');space.className='space';space.dataset.spaceId=String(id);spaces.appendChild(space);
    if(saved.status==='complete'&&saved.payload){workspaceState.set(id,{id,raw:String(saved.raw||''),status:'complete',payload:saved.payload,history:saved.history||[],last_change:saved.last_change||null,refreshed_at:saved.refreshed_at||null});completeSpace(space,saved.payload,String(saved.raw||''),{history:saved.history||[],lastChange:saved.last_change||null,refreshedAt:saved.refreshed_at||null,suppressUpdate:true});}
    else{failSpace(space,String(saved.raw||''),saved.error||'Analysis was incomplete when this workspace was saved.',{history:saved.history||[],suppressUpdate:true});}
  });
  nextSpaceId=Math.max(Number(snapshot.next_space_id)||1,maxId+1);status.textContent=`Workspace restored. ${workspaceState.size} saved space${workspaceState.size===1?'':'s'} loaded without re-analysis.`;updateWorkspace();
}
function clearWorkspace(){workspaceState.clear();spaces.replaceChildren();status.textContent='Workspace cleared.';updateWorkspace();}

form.addEventListener('submit',async e=>{e.preventDefault();const raw=url.value;const targets=parseTargets(raw);if(!targets.length){status.textContent='Nothing to analyze.';return;}go.disabled=true;url.disabled=true;go.textContent=targets.length===1?'Analyzing…':`Analyzing ${targets.length}…`;status.textContent=targets.length===1?'Analyzing 1 target…':`Queued ${targets.length} independent targets…`;url.value='';try{const state=await runBatch(targets);status.textContent=`Done. ${state.ok}/${state.total} completed${state.failed?` · ${state.failed} failed`:''}.`;}finally{go.disabled=false;url.disabled=false;go.textContent='Analyze';url.focus();updateWorkspace();}});
url.addEventListener('keydown',e=>{if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)){e.preventDefault();form.requestSubmit();}});
document.querySelector('#expand-all').addEventListener('click',()=>spaces.querySelectorAll(':scope > .space').forEach(x=>x.open=true));
document.querySelector('#collapse-all').addEventListener('click',()=>spaces.querySelectorAll(':scope > .space').forEach(x=>x.open=false));
document.querySelector('#clear-all').addEventListener('click',clearWorkspace);
updateWorkspace();

window.BookmarkWorkspace={parseTargets,renderWorkspaceIntel,serializeWorkspace,restoreWorkspace,refreshSpaceById,refreshAll,getRelationshipGraph,clearWorkspace};
})();