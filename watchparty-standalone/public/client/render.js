function render() {
  if (!state) return;
  $('roomPill').textContent = displayRoomLabel();
  $('roomPill').title = `Copy join code: ${joinCode || roomId}`;
  $('hostBadge').textContent = isHost() ? (state.temporaryHost ? 'TEMP HOST' : 'YOU ARE HOST') : (state.temporaryHost ? 'TEMP HOST ACTIVE' : '');
  $('deleteRoomBtn').hidden = !isHost();
  $('members').innerHTML = state.members.map(m => { const host = m.id===state.hostId; const owner = m.accountId===state.ownerAccountId; const transfer = isHost() && !host ? `<button class="member-transfer" data-transfer-host="${m.id}" title="Make ${escapeHtml(m.name)} host">Make host</button>` : ''; return `<div class="member-row"><span class="member ${host?'host':''}">${escapeHtml(m.name)}${host?' ★':''}${owner && !host?' 👑':''}</span>${transfer}</div>`; }).join('');
  document.querySelectorAll('[data-transfer-host]').forEach(btn => btn.addEventListener('click', async () => { const targetMemberId = btn.getAttribute('data-transfer-host'); if (!targetMemberId) return; btn.disabled = true; const ok = await command('transfer-host', {targetMemberId}); if (!ok) btn.disabled = false; }));
  $('chat').innerHTML = state.messages.map(m => `<div class="msg"><b>${escapeHtml(m.name)}</b><p>${escapeHtml(m.text)}</p></div>`).join('');
  $('chat').scrollTop = $('chat').scrollHeight;

  const source = state.source || {};
  if (!sourceInputDirty) {
    if (source.kind === 'media') {
      $('sourceInput').value = source.url || source.originalUrl || '';
      if ($('mediaSourceInput') && source.originalUrl && source.originalUrl !== source.url) {
        $('mediaSourceInput').value = source.originalUrl;
      }
    } else {
      $('sourceInput').value = source.originalUrl || (source.videoId ? `https://www.youtube.com/watch?v=${source.videoId}` : '');
    }
    if (typeof updateSourceInputButton === 'function') updateSourceInputButton();
  }
  $('sourceModeLabel').textContent = source.kind === 'media' ? 'External media' : 'YouTube';
  const mediaMeta = $('mediaMeta');
  if (mediaMeta) mediaMeta.textContent = source.kind === 'media' ? [source.title, source.server, source.audio?.toUpperCase(), source.type?.toUpperCase()].filter(Boolean).join(' · ') || 'Direct media' : '';

  if (source.kind === 'media' && window.watchPartyProviders) {
    const provider = window.watchPartyProviders.find(source);
    provider?.load?.(source)?.catch?.(error => setStatus(error?.message || 'Media player failed to initialize.'));
  } else if (source.videoId) {
    window.mediaPlayback?.clear?.();
    ensurePlayer(source.videoId);
  }
}
