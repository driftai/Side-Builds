let resolvedMediaCandidates = [];
function selectedMediaCandidate(){const index=Number($('mediaSourceSelect')?.value);return Number.isInteger(index)?resolvedMediaCandidates[index]:null;}
function onMediaSelectChange(){
  const candidate=selectedMediaCandidate();
  if(candidate?.url && $('sourceInput')){
    $('sourceInput').value=candidate.url;
    if(typeof updateSourceInputButton === 'function') updateSourceInputButton();
  }
}
function mediaCandidateLabel(item){
  const server=String(item.server||item.provider||'Unknown server').trim();
  const audio=String(item.audio||'').toUpperCase();
  const quality=String(item.quality||'').toUpperCase();
  const type=String(item.type||'').toUpperCase();
  return [server,audio,quality,type].filter(Boolean).join(' · ');
}
async function resolveMediaInput(){
  if(!isHost())return alert('Only the host can resolve a media page.');
  const input=$('mediaSourceInput')?.value.trim();
  if(!input)return alert('Paste a direct media URL or a supported watch page URL.');
  const button=$('resolveMediaBtn');
  button.disabled=true;
  setStatus('Finding playable media...');
  try{
    const res=await fetch(apiUrl('/api/media/resolve'),{
      method:'POST',
      headers:{'Content-Type':'application/json','x-member-id':session.memberId},
      body:JSON.stringify({url:input,roomId}),
      cache:'no-store'
    });
    const data=await res.json().catch(()=>({}));
    if(!res.ok||!Array.isArray(data.results)||!data.results.length)return setStatus(data.message||data.error||'No playable media was found.');
    resolvedMediaCandidates=data.results;
    const select=$('mediaSourceSelect');
    select.innerHTML=resolvedMediaCandidates.map((item,index)=>`<option value="${index}">${escapeHtml(mediaCandidateLabel(item))}</option>`).join('');
    $('mediaSourceResults').hidden=false;
    const first=resolvedMediaCandidates[0];
    if(first?.url && $('sourceInput')){
      $('sourceInput').value=first.url;
      if(typeof updateSourceInputButton === 'function') updateSourceInputButton();
    }
    $('mediaMeta').textContent=[data.title,`Found ${resolvedMediaCandidates.length} streams`].filter(Boolean).join(' · ');
    setStatus('Media source found');
  }catch(error){
    setStatus(error?.message||'Media resolver failed.')
  }finally{
    button.disabled=false;
  }
}
async function loadSelectedMedia(){
  if(!isHost())return alert('Only the host can load media.');
  const candidate=selectedMediaCandidate();
  if(!candidate)return alert('Resolve a media page first.');
  const originalUrl=$('mediaSourceInput')?.value.trim()||candidate.url;
  const res=await fetch(apiUrl(`/api/rooms/${roomId}/media-source`),{
    method:'POST',
    headers:{'Content-Type':'application/json','x-member-id':session.memberId},
    body:JSON.stringify({media:candidate,originalUrl})
  });
  const data=await res.json().catch(()=>({}));
  if(!res.ok)return setStatus(data.error||'Could not load media.');
  state=data.state;
  sourceInputDirty=false;
  if($('sourceInput')){
    $('sourceInput').value=candidate.url;
    if(typeof updateSourceInputButton === 'function') updateSourceInputButton();
  }
  render();
  setStatus('Media ready');
}
$('resolveMediaBtn').onclick=resolveMediaInput;
$('loadMediaBtn').onclick=loadSelectedMedia;
$('mediaSourceSelect').onchange=onMediaSelectChange;
