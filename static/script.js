const MAX_SELECT = 20;
const MAX_UPLOAD_FILES = 15;

// TODO: put your real documentation URL here before publishing.
const HELP_URL = "https://github.com/YOUR_USERNAME/YOUR_REPO#readme";

let selected = [];   // ordered list of theme ids, order = slot order
                      // id = plain filename (local upload) or "remote:filename" (GitHub-hosted)

const grid = document.getElementById("grid");
const counter = document.getElementById("counter");
const generateBtn = document.getElementById("generateBtn");
const statusEl = document.getElementById("status");
const downloadLink = document.getElementById("downloadLink");
const uploadBtn = document.getElementById("uploadBtn");
const uploadInput = document.getElementById("uploadInput");
const uploadStatus = document.getElementById("uploadStatus");
const helpBtn = document.getElementById("helpBtn");
const refreshBtn = document.getElementById("refreshBtn");
const themesStatus = document.getElementById("themesStatus");
const updateBanner = document.getElementById("updateBanner");
const updateBannerText = document.getElementById("updateBannerText");
const updateBannerDismiss = document.getElementById("updateBannerDismiss");

helpBtn.href = HELP_URL;

function renderSkeleton(count) {
  grid.innerHTML = "";
  for (let i = 0; i < count; i++) {
    const card = document.createElement("div");
    card.className = "theme-card skeleton";
    card.innerHTML = '<div class="preview-wrap"></div><div class="label">&nbsp;</div>';
    grid.appendChild(card);
  }
}

function setThemesStatus(text, kind) {
  // kind: "" | "error" | "muted" - reuses the same row styling as upload status
  themesStatus.textContent = text || "";
  themesStatus.className = kind || "";
}

async function loadThemes() {
  renderSkeleton(12);
  const res = await fetch("/api/themes");
  const data = await res.json();
  const themes = data.themes || [];

  grid.innerHTML = "";
  themes.forEach(theme => {
    const card = document.createElement("div");
    card.className = "theme-card";
    card.dataset.id = theme.id;
    if (theme.source === "remote") card.classList.add("remote");

    const previewWrap = document.createElement("div");
    previewWrap.className = "preview-wrap";

    const img = document.createElement("img");
    img.src = theme.preview ? `data:${theme.preview_mime};base64,${theme.preview}` : "";
    img.alt = theme.name;
    img.loading = "lazy";
    if (theme.preview) {
      img.addEventListener("load", () => img.classList.add("loaded"));
    } else {
      img.style.opacity = 0.3;
    }
    previewWrap.appendChild(img);

    if (theme.source === "remote") {
      const badge = document.createElement("div");
      badge.className = "cloud-badge";
      badge.title = "Downloaded from GitHub when you generate your backup";
      badge.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
        stroke-linecap="round" stroke-linejoin="round"><path d="M17.5 19H9a6 6 0 1 1 1.2-11.88A5 5 0 0 1 20 9.5a4 4 0 0 1-2.5 9.5Z"/></svg>`;
      previewWrap.appendChild(badge);
    }

    const label = document.createElement("div");
    label.className = "label";
    label.textContent = theme.name;

    card.appendChild(previewWrap);
    card.appendChild(label);
    card.addEventListener("click", () => toggleSelect(theme.id, card));

    grid.appendChild(card);
  });

  return data;
}

function toggleSelect(id, card) {
  const idx = selected.indexOf(id);
  if (idx >= 0) {
    selected.splice(idx, 1);
    card.classList.remove("selected");
  } else {
    if (selected.length >= MAX_SELECT) {
      statusEl.textContent = `You can only select ${MAX_SELECT} themes.`;
      return;
    }
    selected.push(id);
    card.classList.add("selected");
  }
  statusEl.textContent = "";
  counter.textContent = `${selected.length} / ${MAX_SELECT} selected`;
  counter.classList.add("pulse");
  setTimeout(() => { counter.classList.remove("pulse"); }, 200);
  generateBtn.disabled = selected.length === 0;
}

generateBtn.addEventListener("click", async () => {
  generateBtn.disabled = true;
  const remoteCount = selected.filter(id => id.startsWith("remote:")).length;
  statusEl.textContent = remoteCount > 0
    ? `Downloading ${remoteCount} theme${remoteCount === 1 ? "" : "s"} and building...`
    : "Generating backup...";
  downloadLink.style.display = "none";

  const res = await fetch("/api/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ selected })
  });
  const data = await res.json();

  if (data.error) {
    statusEl.textContent = "Error: " + data.error;
    generateBtn.disabled = false;
    return;
  }

  statusEl.textContent = "Done.";
  downloadLink.style.display = "inline";
  generateBtn.disabled = false;
});

// --- remote themes: auto-check on launch + manual refresh -----------------

async function refreshThemes(auto) {
  refreshBtn.disabled = true;
  refreshBtn.classList.add("spinning");
  if (!auto) setThemesStatus("Checking for new themes...", "muted");

  try {
    const res = await fetch("/api/themes/refresh", { method: "POST" });
    const data = await res.json();

    if (!data.ok) {
      // On an automatic (page-load) check, a failure (e.g. offline, or
      // GITHUB_OWNER not filled in yet) should stay silent - the app
      // just keeps using whatever's already loaded/cached.
      if (!auto) setThemesStatus(data.error || "Couldn't check for new themes.", "error");
      return;
    }

    const before = window.__themesManifestVersion;
    const changed = before !== undefined && before !== data.version;
    window.__themesManifestVersion = data.version;

    const reloaded = await loadThemes();
    window.__themesManifestVersion = reloaded.manifest_version;

    if (!auto) {
      setThemesStatus(
        changed || before === undefined
          ? `Up to date - ${data.theme_count} theme(s) available on GitHub.`
          : `No new themes yet - ${data.theme_count} theme(s) available on GitHub.`,
        "muted"
      );
    }
  } catch (err) {
    if (!auto) setThemesStatus("Couldn't check for new themes: " + err, "error");
  } finally {
    refreshBtn.disabled = false;
    refreshBtn.classList.remove("spinning");
  }
}

refreshBtn.addEventListener("click", () => refreshThemes(false));

// --- app update banner ------------------------------------------------------

async function checkAppVersion() {
  try {
    const res = await fetch("/api/app-version");
    const data = await res.json();
    if (data.update_available) {
      updateBannerText.textContent = `A new version (${data.latest}) is available.`;
      updateBanner.dataset.url = data.release_url;
      updateBanner.style.display = "flex";
    }
  } catch (err) {
    // silent - this is a courtesy notice, not core functionality
  }
}

updateBanner.addEventListener("click", (e) => {
  if (e.target === updateBannerDismiss) return;
  const url = updateBanner.dataset.url;
  if (url) window.open(url, "_blank", "noopener");
});
updateBannerDismiss.addEventListener("click", () => {
  updateBanner.style.display = "none";
});

// --- initial load: render from cache instantly, then check for updates ----

loadThemes().then(data => {
  window.__themesManifestVersion = data.manifest_version;
  if (data.remote_enabled) refreshThemes(true);
});
checkAppVersion();

uploadBtn.addEventListener("click", () => uploadInput.click());

uploadInput.addEventListener("change", async () => {
  const files = Array.from(uploadInput.files);
  uploadInput.value = ""; // allow re-selecting the same file later

  if (files.length === 0) return;

  if (files.length > MAX_UPLOAD_FILES) {
    uploadStatus.textContent = `Select at most ${MAX_UPLOAD_FILES} files at a time.`;
    uploadStatus.className = "error";
    return;
  }

  const formData = new FormData();
  files.forEach(f => formData.append("files", f));

  uploadStatus.textContent = "Uploading and validating...";
  uploadStatus.className = "";
  uploadBtn.disabled = true;

  try {
    const res = await fetch("/api/upload", { method: "POST", body: formData });
    const data = await res.json();

    if (data.error) {
      uploadStatus.textContent = data.error;
      uploadStatus.className = "error";
      return;
    }

    const added = data.results.filter(r => r.status === "added");
    const rejected = data.results.filter(r => r.status === "rejected");

    uploadStatus.innerHTML = "";
    uploadStatus.className = "";

    if (added.length) {
      const line = document.createElement("div");
      line.className = "upload-summary";
      line.textContent = `Added ${added.length} theme${added.length === 1 ? "" : "s"}.`;
      uploadStatus.appendChild(line);
    }

    if (rejected.length) {
      uploadStatus.classList.add("error");
      const summary = document.createElement("div");
      summary.className = "upload-summary";
      summary.textContent = `${rejected.length} file${rejected.length === 1 ? "" : "s"} rejected:`;
      uploadStatus.appendChild(summary);

      const list = document.createElement("div");
      list.className = "upload-results";
      rejected.forEach(r => {
        const row = document.createElement("div");
        row.className = "upload-row";
        const name = document.createElement("div");
        name.className = "upload-filename";
        name.textContent = r.filename;
        const reason = document.createElement("div");
        reason.className = "upload-reason";
        reason.textContent = r.reason;
        row.appendChild(name);
        row.appendChild(reason);
        list.appendChild(row);
      });
      uploadStatus.appendChild(list);
    }

    if (!added.length && !rejected.length) {
      uploadStatus.textContent = "No files processed.";
    }

    if (added.length) await loadThemes();
  } catch (err) {
    uploadStatus.textContent = "Upload failed: " + err;
    uploadStatus.className = "error";
  } finally {
    uploadBtn.disabled = false;
  }
});
