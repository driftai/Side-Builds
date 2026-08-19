function filenameFrom(response, fallback) {
  const disposition = response.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="?([^";]+)"?/i);
  return match?.[1] || fallback;
}

async function download(path, fallback) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    let message = `Export failed (${response.status})`;
    try { message = (await response.json()).error || message; } catch (_) {}
    throw new Error(message);
  }
  const blob = await response.blob();
  const href = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = href;
  link.download = filenameFrom(response, fallback);
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(href), 1000);
}

export function setupLibraryTransfer({ exportAllButton, importButton, importInput, onImported, toast }) {
  async function exportAll() {
    try {
      toast?.("Building library ZIP…", "countdown");
      await download("/api/library/export", "Piano-Auto-Player-library.zip");
      toast?.("Library ZIP exported", "complete");
    } catch (error) { toast?.(error.message, "error"); }
  }

  async function exportSong(song) {
    try {
      toast?.(`Exporting ${song.title || "song"}…`, "countdown");
      await download(`/api/library/export-song?id=${encodeURIComponent(song.id)}`, "song.piano-song.json");
      toast?.("Song exported", "complete");
    } catch (error) { toast?.(error.message, "error"); }
  }

  async function importFiles(files) {
    let imported = 0, updated = 0, failures = [];
    for (const file of files) {
      try {
        toast?.(`Importing ${file.name}…`, "countdown");
        const response = await fetch(`/api/library/import?filename=${encodeURIComponent(file.name)}`, {
          method: "POST",
          headers: { "Content-Type": file.type || "application/octet-stream" },
          body: file,
        });
        let data = {};
        try { data = await response.json(); } catch (_) {}
        if (!response.ok) throw new Error(data.error || `Import failed (${response.status})`);
        imported += Number(data.imported || 0);
        updated += Number(data.updated || 0);
        failures.push(...(data.errors || []));
      } catch (error) { failures.push(`${file.name}: ${error.message}`); }
    }
    await onImported?.();
    const suffix = updated ? ` · ${updated} replaced existing` : "";
    const failed = failures.length ? ` · ${failures.length} warning${failures.length === 1 ? "" : "s"}` : "";
    toast?.(`${imported} song${imported === 1 ? "" : "s"} imported${suffix}${failed}`, failures.length && !imported ? "error" : "complete");
  }

  exportAllButton?.addEventListener("click", exportAll);
  importButton?.addEventListener("click", () => importInput?.click());
  importInput?.addEventListener("change", async () => {
    const files = [...(importInput.files || [])];
    importInput.value = "";
    if (files.length) await importFiles(files);
  });

  return { exportAll, exportSong, importFiles };
}
