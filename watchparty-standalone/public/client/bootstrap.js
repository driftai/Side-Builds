function currentPosition() { return mediaVideo ? (mediaVideo.currentTime || 0) : (ytPlayer?.getCurrentTime?.() || 0); }
async function command(type, extra={}) {
  const res = await fetch(apiUrl(`/api/rooms/${roomId}/command`), {method:'POST',headers:{'Content-Type':'application/json','x-member-id':session.memberId},body:JSON.stringify({type,...extra})});
  if (!res.ok) { const d=await res.json().catch(()=>({})); setStatus(d.error || 'Command rejected'); return false; }
  return true;
}

$('createBtn').onclick = async () => {
  await networkInfoReady;
  const name = $('nameInput').value.trim() || 'Guest';
  const requested = $('roomInput').value.trim().toUpperCase();
  const id = requested || makeRoomId();
  if (!/^[A-Z0-9_-]{3,32}$/.test(id)) return alert('Enter a valid room number or room ID');
  setName(name);
  try {
    const res = await fetch(apiUrl(`/api/rooms/${encodeURIComponent(id)}/create`), {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name, accountId, roomCode:/^[0-9]{1,12}$/.test(id) ? id : undefined})});
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return alert(data.error || 'Could not create room');
    await join(data.roomId, name, data.roomCode || null);
  } catch { alert('Could not create room'); }
};
$('joinBtn').onclick = () => { const id=$('roomInput').value.trim(); const name=$('nameInput').value.trim()||'Guest'; if (!/^[A-Za-z0-9_-]{3,32}$/.test(id)) return alert('Enter the room number or encoded room ID'); join(id,name); };
function updateSourceInputButton() {
  const input = $('sourceInput')?.value.trim() || '';
  const btn = $('loadBtn');
  if (!btn) return;
  if (/\.m3u8(?:$|[?#])/i.test(input) || /\.(mp4|webm|m4v|mkv)(?:$|[?#])/i.test(input)) {
    btn.textContent = 'Load Media';
  } else if (/miruro\./i.test(input) || /watch\/[0-9]+/i.test(input)) {
    btn.textContent = 'Find & Load';
  } else {
    btn.textContent = 'Load YouTube';
  }
}
$('sourceInput').addEventListener('input', () => { sourceInputDirty = true; updateSourceInputButton(); });
$('loadBtn').onclick = async () => {
  if (!isHost()) return alert('Only the host can load video sources.');
  const input = $('sourceInput').value.trim();
  if (!input) return alert('Paste a YouTube URL, watch page URL, or direct media URL.');
  if (/\.m3u8(?:$|[?#])/i.test(input) || /\.(mp4|webm|m4v|mkv)(?:$|[?#])/i.test(input)) {
    const isHls = /\.m3u8(?:$|[?#])/i.test(input);
    setStatus('Loading direct media…');
    const res = await fetch(apiUrl(`/api/rooms/${roomId}/media-source`), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-member-id': session.memberId },
      body: JSON.stringify({ media: { url: input, type: isHls ? 'hls' : 'file', server: new URL(input).hostname, title: 'Direct media' }, originalUrl: input })
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return setStatus(data.error || 'Could not load media.');
    state = data.state;
    sourceInputDirty = false;
    render();
    setStatus('Media ready');
    return;
  }
  if (/miruro\./i.test(input) || /watch\/[0-9]+/i.test(input)) {
    if ($('mediaSourceInput')) $('mediaSourceInput').value = input;
    await resolveMediaInput();
    const candidate = selectedMediaCandidate();
    if (candidate) await loadSelectedMedia();
    return;
  }
  const ok = await command('source', { input });
  if (ok) { sourceInputDirty = false; setStatus('Video ready'); }
};
$('syncBtn').onclick = () => {
  if (state?.source?.kind === 'media') window.mediaPlayback?.sync?.({force:true});
  else syncPlayer({force:true});
};
$('copyBtn').onclick = async () => { const link = shareRoomLink(); if (!link) return; setStatus(await copyText(link) ? 'Room link copied' : link); };
$('roomPill').onclick = copyJoinCode;
$('copyLanBtn').onclick = async () => { const link = lanRoomLink(); if (!link) return setStatus('LAN address not available'); setStatus(await copyText(link) ? 'LAN room link copied (physical LAN IP)' : link); };
$('deleteRoomBtn').onclick = async () => { if (!isHost()) return; if (!confirm('Delete this room for everyone?')) return; const ok = await command('delete-room'); if (ok) leaveRoom('Room deleted.'); };
$('chatForm').onsubmit = (e) => { e.preventDefault(); const text=$('chatInput').value.trim(); if(!text)return; command('chat',{text}); $('chatInput').value=''; };
$('nameInput').value = currentName();
networkInfoReady = loadNetworkInfo();
const initialRoom = roomFromUrl();
if (initialRoom) networkInfoReady.then(() => join(initialRoom, currentName()));
window.addEventListener('beforeunload',()=>{
  savePlayerAudioPrefs();
  eventSource?.close();
  if(remotePollTimer)clearInterval(remotePollTimer);
  if(pingTimer)clearInterval(pingTimer);
  if(roomId&&session) {
    const blob = new Blob([JSON.stringify({roomId, memberId:session.memberId})], {type:'application/json'});
    navigator.sendBeacon?.(apiUrl(`/api/rooms/${roomId}/leave?memberId=${encodeURIComponent(session.memberId)}`), blob);
  }
});
