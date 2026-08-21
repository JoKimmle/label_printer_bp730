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

function setUpdateStatus(text, isError) {
  const status = document.getElementById("update-status");
  if (!status) return;
  if (!text) {
    status.hidden = true;
    status.textContent = "";
    status.className = "update-status";
    return;
  }
  status.hidden = false;
  status.textContent = text;
  status.className = isError ? "update-status update-status-error" : "update-status";
}

function resetUpdateButton(btn) {
  btn.disabled = false;
  btn.className = "btn btn-secondary";
  btn.textContent = "Check for updates";
  delete btn.dataset.latest;
  delete btn.dataset.ready;
}

async function checkForUpdates(btn) {
  btn.disabled = true;
  btn.textContent = "Checking…";
  setUpdateStatus("");
  try {
    const resp = await fetch("/api/updates/check");
    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.error || "Update check failed");
    }
    if (data.update_available) {
      btn.disabled = false;
      btn.className = "btn btn-primary";
      btn.textContent = "Update to " + data.latest;
      btn.dataset.latest = data.latest;
      btn.dataset.ready = "1";
      if (!data.installed) {
        setUpdateStatus("Run Install Label Printer Software.command to enable automatic updates.", true);
      } else {
        setUpdateStatus("");
      }
      return;
    }
    btn.textContent = "You’re up to date";
    setTimeout(() => resetUpdateButton(btn), 4000);
  } catch (err) {
    resetUpdateButton(btn);
    setUpdateStatus(err.message || "Update check failed", true);
  }
}

async function applyUpdate(btn) {
  const latest = btn.dataset.latest || "";
  const installed = btn.dataset.installed === "1";
  if (!installed) {
    setUpdateStatus("Run Install Label Printer Software.command to enable automatic updates.", true);
    return;
  }
  const confirmed = window.confirm(
    "Update to " + latest + "? The app will restart. Your designs will be kept."
  );
  if (!confirmed) return;

  btn.disabled = true;
  btn.textContent = "Downloading / installing…";
  setUpdateStatus("The app will restart when the update finishes.");
  try {
    const resp = await fetch("/api/updates/apply", { method: "POST" });
    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.error || "Update failed");
    }
  } catch (err) {
    resetUpdateButton(btn);
    btn.dataset.latest = latest;
    btn.dataset.ready = "1";
    btn.className = "btn btn-primary";
    btn.textContent = "Update to " + latest;
    setUpdateStatus(err.message || "Update failed", true);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("update-check-btn");
  if (!btn) return;
  btn.addEventListener("click", () => {
    if (btn.dataset.ready === "1") {
      applyUpdate(btn);
    } else {
      checkForUpdates(btn);
    }
  });
});

