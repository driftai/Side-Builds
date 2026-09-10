(function () {
'use strict';

const MAX_CHANGES=80;
const text=v=>String(v==null?'':v).replace(/\s+/g,' ').trim();
const norm=v=>text(v).toLowerCase();
const key=v=>norm(v).replace(/[^a-z0-9]+/g,'_').replace(/^_+|_+$/g,'');

function scalar(value){
  if(value==null)return'';
  if(['string','number','boolean'].includes(typeof value))return text(value).slice(0,700);
  if(Array.isArray(value)&&value.every(v=>['string','number','boolean'].includes(typeof v)))return value.map(text).filter(Boolean).sort((a,b)=>a.localeCompare(b)).join(' · ').slice(0,1200);
  return'';
}

function put(map,path,label,value){
  const rendered=scalar(value);
  if(rendered)map.set(path,{label,value:rendered});
}

function putSet(map,path,label,rows){
  const values=[...new Set((rows||[]).map(text).filter(Boolean))].sort((a,b)=>a.localeCompare(b));
  if(values.length)map.set(path,{label,value:values.join(' · ').slice(0,2500)});
}

function flattenSection(map,name,obj,prefix='',depth=0){
  if(!obj||typeof obj!=='object'||depth>2)return;
  Object.entries(obj).forEach(([field,value])=>{
    const pathPart=key(field); if(!pathPart)return;
    const path=`section.${key(name)}.${prefix}${pathPart}`;
    const label=`${name} · ${field}`;
    const rendered=scalar(value);
    if(rendered){put(map,path,label,rendered);return;}
    if(value&&typeof value==='object'&&!Array.isArray(value))flattenSection(map,name,value,`${prefix}${pathPart}.`,depth+1);
  });
}

function addSearchSynthesis(map,data){
  const research=data.search_research||{},synthesis=research.synthesis||{};
  if(!synthesis.version)return;
  put(map,'search_synthesis.confidence','Search synthesis confidence',Math.round((Number(synthesis.confidence)||0)*100)+'%');
  put(map,'search_synthesis.top_source','Top research source',synthesis.top_source_title);
  put(map,'search_synthesis.warning_count','Search source-quality warnings',synthesis.warning_count);
  putSet(map,'search_synthesis.warnings','Search source-quality warning details',(synthesis.warnings||[]).map(w=>`${text(w&&w.title)} — ${text(w&&w.reason)}`));
  putSet(map,'search_synthesis.ranking','Search evidence ranking',(research.source_ranking||[]).slice(0,7).map(r=>`${r.rank}. ${text(r.title)} · evidence ${r.evidence_score} · primary ${r.primary_content_confidence} · ${r.synthesis_eligible?'eligible':'provenance only'}`));
}

function semanticSnapshot(payload){
  const data=payload&&payload.data||{};
  const map=new Map();
  put(map,'identity.title','Title',data.identity&&data.identity.title);
  put(map,'classification.kind','Type',data.classification&&data.classification.kind);
  put(map,'classification.category','Category',data.classification&&data.classification.category);
  put(map,'bookmark.folder','Suggested folder',data.bookmark&&data.bookmark.suggested_folder);
  put(map,'summary','Summary',data.summary);

  const quality=Number(data.quality&&data.quality.extraction_score);
  if(Number.isFinite(quality))map.set('quality.extraction',{label:'Extraction quality',value:String(Math.round(quality*100))+'%'});

  (data.key_facts||[]).forEach(f=>put(map,`fact.${key(f&&f.label)}`,`Fact · ${text(f&&f.label)}`,f&&f.value));
  Object.entries(data.sections||{}).forEach(([name,obj])=>flattenSection(map,name,obj));

  const compiled=data.search_research&&data.search_research.compiled_facts||[];
  compiled.forEach(group=>{
    const values=(group&&group.values||[]).map(v=>v&&v.value).filter(v=>v!=null);
    putSet(map,`search_fact.${key(group&&group.label)}`,`Search fact · ${text(group&&group.label)}`,values);
  });
  addSearchSynthesis(map,data);

  putSet(map,'tags','Tags',data.tags||[]);
  putSet(map,'entities','Entities',(data.entities||[]).map(e=>`${text(e&&e.type)}: ${text(e&&e.name)}`));
  putSet(map,'important_links','Selected / important links',(((data.links||{}).important)||[]).map(link=>`${text(link&&link.label)} — ${text(link&&link.url)}`));
  return map;
}

function meaningfulQualityChange(before,after){
  const a=parseInt(String(before||'').replace(/\D/g,''),10),b=parseInt(String(after||'').replace(/\D/g,''),10);
  return Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)>=5;
}

function comparePayloads(beforePayload,afterPayload){
  const before=semanticSnapshot(beforePayload),after=semanticSnapshot(afterPayload);
  const paths=[...new Set([...before.keys(),...after.keys()])].sort();
  const changes=[];
  paths.forEach(path=>{
    const a=before.get(path),b=after.get(path);
    if(!a&&b){changes.push({type:'added',path,label:b.label,before:'',after:b.value});return;}
    if(a&&!b){changes.push({type:'removed',path,label:a.label,before:a.value,after:''});return;}
    if(!a||!b||norm(a.value)===norm(b.value))return;
    if(path==='quality.extraction'&&!meaningfulQualityChange(a.value,b.value))return;
    changes.push({type:'changed',path,label:b.label||a.label,before:a.value,after:b.value});
  });
  return {
    checked_at:new Date().toISOString(),
    count:Math.min(changes.length,MAX_CHANGES),
    truncated:changes.length>MAX_CHANGES,
    changes:changes.slice(0,MAX_CHANGES)
  };
}

window.BookmarkChanges={comparePayloads,semanticSnapshot};
})();
