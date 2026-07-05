/** Save preview PNG without navigating away (pywebview-safe). */
async function downloadPreview(token, filename) {
  const status = document.getElementById("download-status");
  if (status) {
    status.textContent = "";
    status.className = "download-status";
  }

  try {
    if (window.pywebview?.api?.download_preview) {
      const result = await window.pywebview.api.download_preview(token);
      if (!status) return;
      if (result.ok) {
        status.textContent = "Saved";
        status.classList.add("download-status-ok");
      } else if (result.cancelled) {
        status.textContent = "";
      } else {
        status.textContent = result.error || "Download failed";
        status.classList.add("download-status-error");
      }
      return;
    }

    const resp = await fetch("/download/" + encodeURIComponent(token));
    if (!resp.ok) throw new Error("Download failed");
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.style.display = "none";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    if (status) {
      status.textContent = "Saved";
      status.classList.add("download-status-ok");
    }
  } catch (err) {
    if (status) {
      status.textContent = "Download failed";
      status.classList.add("download-status-error");
    }
  }
}
