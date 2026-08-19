const pct = value => `${(Number(value || 0) * 100).toFixed(1)}%`;
const ms = value => `${Number(value || 0).toFixed(1)} ms`;

export function setupHifiConfidence() {
  const disclosure = document.getElementById("hifiConfidenceDisclosure");
  const summary = document.getElementById("hifiConfidenceSummary");
  const metrics = document.getElementById("hifiConfidenceMetrics");
  const heatmap = document.getElementById("hifiConfidenceHeatmap");
  const review = document.getElementById("hifiConfidenceWorst");

  function show(raw = null) {
    const data = raw?.transcription_diagnostics || raw || {};
    const windows = Array.isArray(data.hifi_windows) ? data.hifi_windows : [];
    if (!windows.length) {
      if (summary) summary.textContent = data.hifi_specialist_notes ? "specialist only · no cross-model map" : "awaiting Auto Hi-Fi conversion";
      if (metrics) metrics.textContent = data.hifi_specialist_notes ? "Cross-model confidence sensors require Auto Hi-Fi (Transkun + Basic Pitch)." : "Run an Auto Hi-Fi conversion to populate agreement and onset sensors.";
      if (heatmap) heatmap.replaceChildren();
      if (review) review.textContent = "";
      return;
    }
    const agreement = pct(data.hifi_agreement_f1);
    const specialist = pct(data.hifi_specialist_coverage);
    const basic = pct(data.hifi_basic_coverage);
    const offset = Number(data.hifi_onset_median_offset_ms || 0);
    const offsetText = `${offset >= 0 ? "+" : ""}${offset.toFixed(1)} ms`;
    const p95 = ms(data.hifi_onset_p95_abs_ms);
    const reviewCount = Number(data.hifi_review_window_count || 0);
    if (summary) summary.textContent = `${agreement} agreement · ${reviewCount} review window${reviewCount === 1 ? "" : "s"}`;
    if (metrics) {
      const corrected = Number(data.hifi_pitch_corrections || 0);
      const pruned = Number(data.hifi_precision_pruned_notes || 0);
      const refinement = corrected || pruned ? ` · precision pass ${corrected} corrected / ${pruned} removed` : "";
      metrics.textContent = `Raw agreement ${agreement} · Transkun matched ${specialist} · Basic Pitch matched ${basic} · median onset offset ${offsetText} · onset P95 ${p95}${refinement}`;
    }
    renderWindows(windows);
    renderReview(windows);
    if (disclosure && reviewCount > 0) disclosure.open = true;
  }

  function renderWindows(windows) {
    if (!heatmap) return;
    heatmap.replaceChildren();
    for (const row of windows) {
      const bar = document.createElement("span");
      bar.className = `hifi-window hifi-${row.level || "silent"}`;
      const score = row.confidence_proxy == null ? "silent" : `${pct(row.confidence_proxy)} confidence proxy`;
      const agreement = row.agreement_f1 == null ? "n/a" : pct(row.agreement_f1);
      const timing = row.onset_p95_abs_ms == null ? "n/a" : ms(row.onset_p95_abs_ms);
      bar.title = `${clock(row.start_ms)}–${clock(row.end_ms)} · ${score} · agreement ${agreement} · onset P95 ${timing} · Transkun ${row.specialist_notes || 0} / Basic ${row.basic_notes || 0}`;
      bar.setAttribute("aria-label", bar.title);
      heatmap.append(bar);
    }
  }

  function renderReview(windows) {
    if (!review) return;
    const candidates = windows
      .filter(row => row.level === "review")
      .sort((a, b) => Number(a.confidence_proxy || 0) - Number(b.confidence_proxy || 0))
      .slice(0, 6);
    if (!candidates.length) {
      review.textContent = "No dense 5-second window fell into the review band. Sparse passages remain marked separately.";
      return;
    }
    review.textContent = `Lowest-agreement regions: ${candidates.map(row => `${clock(row.start_ms)}–${clock(row.end_ms)} (${pct(row.confidence_proxy)})`).join(" · ")}`;
  }

  return { show };
}

function clock(value) {
  const seconds = Math.max(0, Math.round(Number(value || 0) / 1000));
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, "0")}`;
}
