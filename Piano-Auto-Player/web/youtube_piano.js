import { api } from "./api.js";
import { setupHifiConfidence } from "./hifi_confidence.js";

const wait = (ms) => new Promise(resolve => setTimeout(resolve, ms));

export function setupYoutubePiano({ form, input, message, button, searchInput, onSong }) {
  let running = false;
  const access = document.getElementById("youtubeAccessMode");
  const quality = document.getElementById("youtubeQualityMode");
  const engine = document.getElementById("youtubeEngineMode");
  const route = document.getElementById("mediaRouteMode");
  const layout = document.getElementById("pianoLayout");
  const alternateQuery = document.getElementById("alternateSourceQuery");
  const alternateButton = document.getElementById("alternateSourceBtn");
  const alternateMessage = document.getElementById("alternateSourceMessage");
  const alternateResults = document.getElementById("alternateSourceResults");
  const alternateDisclosure = document.querySelector(".alternate-source-disclosure");
  const retryActions = document.getElementById("youtubeRetryActions");
  const confidence = setupHifiConfidence();

  async function refreshDependencies() {
    try {
      const deps = await api.youtubeDependencies();
      if (deps.ready) {
        const runtime = `${deps.js_runtime_name || "JS"}${deps.js_runtime_version ? ` ${deps.js_runtime_version}` : ""}`;
        const ytdlp = deps.yt_dlp_version ? ` · yt-dlp ${deps.yt_dlp_version}` : " · yt-dlp";
        const pot = deps.po_provider ? ` · ${deps.po_provider_name || "PO"} ${deps.po_provider_version || ""}`.trimEnd() : " · PO helper not installed";
        const search = deps.alternate_search?.ready ? " · public-copy search ready" : " · alternate search needs setup";
        const hifi = deps.hifi_ready ? ` · Transkun ${deps.hifi_version || ""} (${deps.hifi_device || "cpu"})` : " · Hi-Fi piano optional setup not installed";
        message.textContent = `Ready · live media transcription${ytdlp} + ${runtime} challenge solver + Basic Pitch${hifi}${pot}${search}`;
        button.disabled = false;
      } else {
        const missing = [!deps.venv && "transcriber", !deps.basic_pitch && "Basic Pitch", !deps.ffmpeg && "FFmpeg", !deps.ffprobe && "FFprobe", !deps.js_runtime && (deps.js_runtime_issue || "YouTube JS runtime")].filter(Boolean).join(" + ");
        message.textContent = `Media-to-Piano setup needs repair${missing ? `: ${missing}` : ""}. Run setup-youtube-piano.bat once, then restart start.bat.`;
        button.disabled = false;
      }
    } catch (error) { message.textContent = error.message; }
  }

  function hostKind(value) {
    try {
      const host = new URL(value).hostname.toLowerCase();
      if (host === "open.spotify.com" || host === "spotify.link" || host.endsWith(".spotify.com")) return "spotify";
      if (host === "youtu.be" || host === "youtube.com" || host.endsWith(".youtube.com")) return "youtube";
      return "public";
    } catch { return "unknown"; }
  }

  async function resolveMedia(value, fallbackTitle = "") {
    try {
      const meta = await api.resolveMedia(value);
      if (!meta.query && fallbackTitle) meta.query = fallbackTitle;
      return meta;
    } catch (_) {
      return { kind: hostKind(value), title: fallbackTitle, artist: "", query: fallbackTitle, direct_audio: hostKind(value) !== "spotify", url: value };
    }
  }

  const diagBtn = document.getElementById("runDiagnosticsBtn");
  const sessionBtn = document.getElementById("openSessionModalBtn");
  const diagOutput = document.getElementById("youtubeDiagOutput");
  const sessionState = document.getElementById("youtubeSessionState");

  if (diagBtn && diagOutput) {
    diagBtn.addEventListener("click", async () => {
      diagOutput.style.display = "block";
      diagOutput.textContent = "Gathering YouTube access diagnostics…";
      try {
        const data = await api.youtubeDiagnostics(input?.value || "");
        const deps = data.dependencies || {};
        const profiles = data.profiles || {};
        const session = data.session || {};
        const lines = [
          `yt-dlp version: ${deps.yt_dlp_version || "unknown"}`,
          `JS runtime: ${deps.js_runtime_name || "none"} ${deps.js_runtime_version || ""}`,
          `PO Token Provider: ${deps.po_provider ? `${deps.po_provider_name} ${deps.po_provider_version}` : "none"}`,
          `Hi-Fi piano: ${deps.hifi_ready ? `Transkun ${deps.hifi_version || ""} · ${deps.hifi_device || "cpu"}` : deps.hifi_issue || "not installed"}`,
          `Windows App-Bound Encryption (v20): Active (DPAPI blocked on Windows Chrome 127+)`,
          `\n=== Browser Profiles ===`,
        ];
        for (const [bName, pList] of Object.entries(profiles)) {
          lines.push(`[${bName.toUpperCase()}]`);
          if (!pList.length) lines.push(`  (no profiles detected)`);
          for (const p of pList) {
            lines.push(`  - ${p.profile} (${p.name}): signed-in=${p.is_signed_in} | user=${p.user_name || "none"} | db=${p.db_status}`);
          }
        }
        lines.push(`\n=== Live Session Bridge ===`);
        lines.push(`Active cookies: ${session.total_cookies || 0}`);
        lines.push(`Account cookies detected: ${session.has_account_cookies ? "YES" : "NO"}`);
        if (session.account_cookie_names?.length) lines.push(`Account keys: ${session.account_cookie_names.join(", ")}`);
        diagOutput.textContent = lines.join("\n");
      } catch (err) { diagOutput.textContent = `Diagnostic error: ${err.message}`; }
    });
  }

  const clearSessionBtn = document.getElementById("clearSessionBtn");

  async function updateSessionUI() {
    try {
      const payload = await api.youtubeSession();
      const s = payload?.session || payload || {};
      const localKey = "piano_youtube_session";
      const legacyLocal = localStorage.getItem(localKey);
      if ((!s.total_cookies) && legacyLocal) {
        try { await api.saveYoutubeSession(legacyLocal); } catch (_) {}
        finally { localStorage.removeItem(localKey); }
        return updateSessionUI();
      }
      if (legacyLocal) localStorage.removeItem(localKey);
      if (clearSessionBtn) clearSessionBtn.style.display = s.total_cookies > 0 ? "inline-block" : "none";
      if (sessionState) {
        const account = s.has_account_cookies ? " · signed-in account cookies" : "";
        sessionState.textContent = s.total_cookies > 0
          ? `Saved session: ${s.total_cookies} cookies retained locally${account}`
          : "Saved session: none — Automatic will use anonymous fallbacks until you import one.";
      }
    } catch (_) {
      if (sessionState) sessionState.textContent = "Saved session status unavailable.";
    }
  }

  if (clearSessionBtn) {
    clearSessionBtn.addEventListener("click", async () => {
      try {
        await api.clearYoutubeSession();
        localStorage.removeItem("piano_youtube_session");
        clearSessionBtn.style.display = "none";
        message.textContent = "Saved YouTube session cookies cleared.";
        updateSessionUI();
        if (diagOutput && diagOutput.style.display !== "none") diagBtn?.click();
      } catch (err) { message.textContent = `Failed to clear session: ${err.message}`; }
    });
  }

  updateSessionUI();

  async function importSession(url = input?.value, titleHint = "") {
    const raw = prompt("Paste your YouTube cookie text (Netscape format or raw Cookie: header from browser DevTools / document.cookie):");
    if (!raw || !raw.trim()) return;
    try {
      message.textContent = "Validating and importing YouTube session cookies…";
      const res = await api.saveYoutubeSession(raw.trim());
      localStorage.removeItem("piano_youtube_session");
      if (clearSessionBtn) clearSessionBtn.style.display = "inline-block";
      const s = res.session || {};
      if (access) access.value = "session";
      message.textContent = `Live YouTube session retained & active (${s.total_cookies} cookies${s.has_account_cookies ? " · account cookies confirmed" : ""}) · converting…`;
      await updateSessionUI();
      if (url) await transcribe(url, titleHint, { allowFallback: false, accessOverride: "session" });
    } catch (err) { message.textContent = `Session import failed: ${err.message}`; }
  }

  if (sessionBtn) {
    sessionBtn.addEventListener("click", () => importSession());
  }

  function clearRetryActions() {
    if (retryActions) retryActions.replaceChildren();
  }

  function showAuthRetries(url, titleHint) {
    if (!retryActions) return;
    retryActions.replaceChildren();
    const label = document.createElement("span");
    label.className = "muted";
    label.textContent = "Retry this exact YouTube video with your signed-in browser (recent profiles are auto-tried):";
    retryActions.append(label);

    const importBtn = document.createElement("button");
    importBtn.type = "button";
    importBtn.className = "primary small";
    importBtn.textContent = "Import Live Session (Paste Cookies)";
    importBtn.addEventListener("click", () => importSession(url, titleHint));
    retryActions.append(importBtn);

    for (const browser of ["chrome", "edge", "firefox"]) {
      const retry = document.createElement("button");
      retry.type = "button";
      retry.className = "ghost small";
      retry.textContent = `Retry with ${browser[0].toUpperCase()}${browser.slice(1)}`;
      retry.addEventListener("click", () => {
        if (access) access.value = browser;
        transcribe(url, titleHint, { allowFallback: false, accessOverride: browser });
      });
      retryActions.append(retry);
    }
  }

  function isBotChallenge(error) {
    const text = String(error?.message || error || "").toLowerCase();
    return text.includes("bot verification challenge") || text.includes("not a bot") || text.includes("--cookies-from-browser") || text.includes("login_required");
  }

  async function transcribe(url = input.value, titleHint = "", options = {}) {
    if (running) return;
    const value = String(url || "").trim();
    if (!value) { message.textContent = "Paste a YouTube, Spotify, or supported public media URL first."; return; }
    input.value = value;
    clearRetryActions();
    running = true; button.disabled = true; button.textContent = "Resolving…";
    let fallbackQuery = "";
    let meta = { kind: hostKind(value), query: titleHint, title: titleHint, artist: "", direct_audio: true };
    const routeMode = route?.value || "live";
    try {
      meta = await resolveMedia(value, titleHint);
      const resolvedTitle = String(titleHint || meta.query || meta.title || "").trim();
      if (resolvedTitle && alternateQuery) alternateQuery.value = resolvedTitle;

      if (meta.kind === "spotify") {
        message.textContent = `Spotify track resolved${resolvedTitle ? ` · ${resolvedTitle}` : ""} · finding a public recording to transcribe live…`;
        const rows = await discover(resolvedTitle, { autoUse: true, spotify: true });
        if (!rows.length) message.textContent = `Spotify track resolved${resolvedTitle ? ` · ${resolvedTitle}` : ""}, but no supported public audio/video copy was found. No sheet or MIDI was substituted.`;
        return;
      }

      button.textContent = "Starting…";
      const accessMode = options.accessOverride || access?.value || "auto";
      const job = await api.startYoutube(value, accessMode, resolvedTitle, quality?.value || "rhythm_accurate", layout?.value || "61", engine?.value || "auto_hifi");
      let state = job;
      while (!["complete", "error"].includes(state.status)) {
        message.textContent = state.message || "Working…";
        await wait(700);
        state = await api.youtubeStatus(job.id);
      }
      if (state.status === "error") throw new Error(state.message || "Media transcription failed.");
      message.textContent = "Live transcription ready · loading timed piano performance…";
      await onSong(state.result, { provider_name: "Live audio/video transcription", url: value });
      confidence.show(state.result);
      const method = state.result?.youtube_access_method ? ` · ${state.result.youtube_access_method}` : "";
      const cleanup = state.result?.transcription_quality_label ? ` · ${state.result.transcription_quality_label}` : "";
      const fields = [["hifi_model_agreements", "raw cross-model matches"], ["hifi_pitch_corrections", "precision pitch corrections"], ["hifi_precision_pruned_notes", "precision extras removed"], ["hifi_sustain_stitches", "held-note stitches"], ["hifi_sustain_reattacks_protected", "confirmed reattacks protected"], ["hifi_sustain_context_reattacks_protected", "chord-context reattacks protected"], ["hifi_sustain_pedal_reattacks_protected", "pedal-held reattacks protected"], ["hifi_sustain_weak_context_stitches", "weak-context holds restored"], ["hifi_sustain_acoustic_reattacks_protected", "acoustic reattacks protected"], ["hifi_sustain_continuity_stitches", "continuity jumps suppressed"], ["hifi_sustain_microgap_stitches", "micro-gap jumps suppressed"], ["hifi_timing_clusters_adjusted", "timing clusters aligned"], ["hifi_timing_adjustments_capped", "timing shifts capped"], ["hifi_timing_early_shifts_guarded", "early timing pulls guarded"], ["hifi_timing_relative_slew_limited", "relative timing jumps softened"], ["hifi_timing_phrase_resets", "phrase timing resets"], ["hifi_timing_sparse_resets", "sparse timing resets"], ["hifi_timing_sparse_slew_limited", "sparse timing jumps softened"], ["hifi_timing_texture_flicker_suppressed", "texture flicker resets suppressed"], ["hifi_sparse_timing_clusters", "sparse timing anchors"], ["hifi_sparse_acoustic_bypassed", "sparse false delays bypassed"], ["hifi_sparse_attack_rescues", "sparse missing attacks rescued"], ["hifi_acoustic_clusters_delayed", "acoustic onset corrections"], ["hifi_acoustic_dense_delays", "dense early attacks delayed"], ["hifi_attack_release_overhang_guarded", "release overhangs guarded"], ["hifi_release_secondary_tails_ignored", "secondary pedal tails ignored"], ["hifi_release_secondary_shorter_ignored", "secondary early releases ignored"], ["hifi_basic_rescued_notes", "cross-model gap rescue"], ["hifi_range_compacted_notes", "61-key edge notes compacted"], ["hifi_range_collision_merges", "range collisions merged"], ["hifi_range_white_collision_merges", "white-key alias collisions resolved"], ["hifi_range_black_collision_merges", "black-key alias collisions resolved"], ["hifi_range_alias_tails_ignored", "folded alias tails ignored"], ["hifi_range_alias_retriggers_suppressed", "folded alias retriggers suppressed"], ["hifi_range_alias_holds_trimmed", "folded alias holds trimmed"], ["consensus_rejected_notes", "consensus rejected"], ["consensus_precision_rescued_notes", "precision rescue"], ["consensus_rescue_suppressed", "rescue candidates suppressed"], ["consensus_spectral_pruned_notes", "spectral guard removed"], ["cleanup_ghost_drops", "ghost guard removed"], ["cleanup_layout_drops", "target range removed"], ["cleanup_sustain_joins", "sustain repair joined"], ["cleanup_dense_reattacks_preserved", "dense reattacks preserved"], ["cleanup_stability_drops", "stability guard removed"]];
      const details = fields.map(([key, label]) => Number(state.result?.[key] || 0) ? ` · ${label} ${Number(state.result[key])}` : "").join("");
      const model = state.result?.transcription_engine ? ` · engine ${state.result.transcription_engine}` : "";
      const sourceSpace = state.result?.hifi_source_space_layout ? ` · ${state.result.hifi_source_space_layout}-key source-space fusion` : "";
      const agreement = Number(state.result?.hifi_agreement_f1 || 0) ? ` · model agreement ${(Number(state.result.hifi_agreement_f1) * 100).toFixed(1)}%` : "";
      const fallback = state.result?.hifi_fallback ? ` · Hi-Fi fallback ${state.result.hifi_fallback}` : "";
      message.textContent = `Loaded from the submitted source${method}${cleanup}${model}${sourceSpace}${agreement}${details}${fallback} · preview with Internal play before sending it to Roblox.`;
    } catch (error) {
      message.textContent = error.message;
      if (meta.kind === "youtube" && isBotChallenge(error)) showAuthRetries(value, String(meta.query || titleHint || ""));
      if (options.allowFallback !== false && meta.kind === "youtube" && routeMode === "fallback") {
        fallbackQuery = String(meta.query || titleHint || alternateQuery?.value || searchInput?.value || "").trim();
      }
    } finally {
      running = false; button.disabled = false; button.textContent = "Convert to piano";
    }
    if (fallbackQuery) await discover(fallbackQuery, { autoUse: true, excludeUrl: value });
  }

  async function discover(query = alternateQuery?.value, options = {}) {
    const value = String(query || "").trim();
    if (!value || !alternateResults || !alternateMessage) return [];
    if (alternateDisclosure) alternateDisclosure.open = true;
    alternateQuery.value = value; alternateResults.innerHTML = ""; alternateButton.disabled = true;
    alternateMessage.textContent = options.spotify ? "Searching public recordings for the Spotify track…" : options.autoUse ? "Exact source unavailable · searching alternate public recordings…" : "Searching public audio/video sources…";
    let rows = [];
    try {
      const data = await api.alternateSources(value);
      rows = (data.results || []).filter(row => !options.excludeUrl || row.url !== options.excludeUrl);
      alternateMessage.textContent = rows.length ? `${rows.length} alternate public source${rows.length === 1 ? "" : "s"} found.` : "No supported alternate public audio/video sources found.";
      for (const row of rows) alternateResults.append(buildAlternateRow(row, value));
      const exact = options.autoUse ? rows.find(row => row.confidence === "exact" && Number(row.score || 0) >= 7.5) : null;
      if (exact) {
        alternateMessage.textContent = `Exact ${exact.host || "public"} recording match found · transcribing that audio…`;
        message.textContent = `Switching to ${exact.host || "an alternate public recording"} for live transcription…`;
        await transcribe(exact.url, exact.title || value, { allowFallback: false });
      } else if (options.autoUse && rows.length) {
        message.textContent = `${rows.length} public recording${rows.length === 1 ? "" : "s"} found below. Choose the matching recording to transcribe.`;
      }
    } catch (error) { alternateMessage.textContent = error.message; }
    finally { alternateButton.disabled = false; }
    return rows;
  }

  function buildAlternateRow(row, titleHint) {
    const item = document.createElement("div"); item.className = "alternate-source-row";
    const copy = document.createElement("div"); copy.className = "alternate-source-copy";
    const title = document.createElement("strong"); title.textContent = row.title || titleHint;
    const confidence = row.confidence && row.confidence !== "candidate" ? ` · ${row.confidence} match` : "";
    const sub = document.createElement("span"); sub.textContent = `${row.host || "Web"}${confidence}${row.snippet ? ` · ${row.snippet}` : ""}`;
    const actions = document.createElement("div"); actions.className = "result-actions";
    const use = document.createElement("button"); use.type = "button"; use.className = "primary small"; use.textContent = "Transcribe"; use.addEventListener("click", () => transcribe(row.url, row.title || titleHint, { allowFallback: false }));
    const open = document.createElement("button"); open.type = "button"; open.className = "ghost small"; open.textContent = "Open"; open.addEventListener("click", () => window.open(row.url, "_blank", "noopener"));
    copy.append(title, sub); actions.append(use, open); item.append(copy, actions); return item;
  }

  form.addEventListener("submit", event => { event.preventDefault(); transcribe(); });
  alternateButton?.addEventListener("click", () => discover());
  refreshDependencies();
  return { transcribe, discover, refreshDependencies, showDiagnostics: confidence.show };
}
