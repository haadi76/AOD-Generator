"""
AOD Theme Manager - local Flask backend.

Folder layout expected next to this file:

    original_source/apps/com.miui.aod/...      <- pristine apps folder (never modified)
    themes/                                     <- pool of .aodbackup (zip) theme files
    work/                                       <- scratch copy, regenerated on every build
    output/                                     <- final .bak files served for download

Core rule that fixes the "website file looks identical but HyperOS rejects it"
problem: theme files are NEVER opened/rewritten with the zipfile module when
they are placed into the apps folder. They are copied byte-for-byte
(shutil.copyfile), exactly like dragging a file over in MT Manager. zipfile is
only ever used read-only, to peek inside a theme zip and pull out the preview
image - it never touches the copy that ends up in the backup.
"""

import os
import io
import json
import time
import shutil
import zipfile
import base64
import hashlib
import tarfile
import subprocess
import urllib.request
import urllib.parse
import urllib.error
from flask import Flask, jsonify, request, send_file, render_template

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
THEMES_DIR = os.path.join(BASE_DIR, "themes")
ORIGINAL_SOURCE_DIR = os.path.join(BASE_DIR, "original_source")  # contains "apps" folder
WORK_DIR = os.path.join(BASE_DIR, "work")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
PRISTINE_SLOTS_DIR = os.path.join(BASE_DIR, "pristine_slots")

# ---------------------------------------------------------------------------
# Remote themes library (GitHub-hosted)
#
# Fill these three in once you've created the repo + a Release for the theme
# files. Until GITHUB_OWNER is changed from its placeholder, every remote
# feature below quietly no-ops and the app behaves exactly as it did before -
# only the themes/ folder (local uploads) is used.
#
#   GITHUB_OWNER / GITHUB_REPO  - your GitHub username/org and repo name
#   GITHUB_BRANCH                - branch that themes_manifest.json + version.json live on
#   RELEASE_TAG                  - tag of the Release you upload .aodbackup files to as assets
#
# See build_manifest.py for how to generate themes_manifest.json from a
# folder of theme files, and what to upload where.
# ---------------------------------------------------------------------------
GITHUB_OWNER = "haadi76"
GITHUB_REPO = "AOD-Generator"
GITHUB_BRANCH = "main"
RELEASE_TAG = "themes"

REMOTE_ENABLED = GITHUB_OWNER != "YOUR_GITHUB_USERNAME" and GITHUB_REPO != "YOUR_REPO_NAME"

MANIFEST_URL = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_BRANCH}/themes_manifest.json"
APP_VERSION_URL = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_BRANCH}/version.json"
RELEASE_ASSET_BASE = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/download/{RELEASE_TAG}"

CURRENT_APP_VERSION = "1.0.0"

REMOTE_CACHE_DIR = os.path.join(BASE_DIR, "remote_cache")
REMOTE_THEMES_DIR = os.path.join(REMOTE_CACHE_DIR, "theme_files")
MANIFEST_CACHE_PATH = os.path.join(REMOTE_CACHE_DIR, "manifest_cache.json")

APP_THEMES_REL = os.path.join(
    "apps", "com.miui.aod", "miui_att", "data", "user_de", "0",
    "com.miui.aod", "app_themes"
)

FIRST_N = 20          # only the first 20 slots (by sorted filename) get replaced
PREVIEW_NAMES = ("preview_aod_0.png", "preview_aod_0.jpg", "preview_aod_0.jpeg")

THEME_EXTS = (".aodbackup", ".zip")

CANONICAL_MEMBER_ORDER = [
    "apps/com.miui.aod/_manifest",
    "apps/com.miui.aod/miui_meta/cache/_tmp_meta",
    "apps/com.miui.aod/miui_bak/_tmp_bak",
    "apps/com.miui.aod/miui_att/data/user_de/0/com.miui.aod/app_themes/2023_2_19_102013_781436854.aodBackup",
    "apps/com.miui.aod/miui_att/data/user_de/0/com.miui.aod/app_themes/2023_2_19_11442_349683353.aodBackup",
    "apps/com.miui.aod/miui_att/data/user_de/0/com.miui.aod/app_themes/2023_2_19_11511_1763837450.aodBackup",
    "apps/com.miui.aod/miui_att/data/user_de/0/com.miui.aod/app_themes/2023_2_19_11527_133657307.aodBackup",
    "apps/com.miui.aod/miui_att/data/user_de/0/com.miui.aod/app_themes/2023_2_19_11550_807582486.aodBackup",
    "apps/com.miui.aod/miui_att/data/user_de/0/com.miui.aod/app_themes/2023_2_19_11610_1276465330.aodBackup",
    "apps/com.miui.aod/miui_att/data/user_de/0/com.miui.aod/app_themes/2023_2_19_11628_1205441905.aodBackup",
    "apps/com.miui.aod/miui_att/data/user_de/0/com.miui.aod/app_themes/2023_2_19_11647_1997927120.aodBackup",
    "apps/com.miui.aod/miui_att/data/user_de/0/com.miui.aod/app_themes/2023_2_19_1179_1083859631.aodBackup",
    "apps/com.miui.aod/miui_att/data/user_de/0/com.miui.aod/app_themes/2023_2_19_11728_1160491222.aodBackup",
    "apps/com.miui.aod/miui_att/data/user_de/0/com.miui.aod/app_themes/2023_2_19_1182_1697936065.aodBackup",
    "apps/com.miui.aod/miui_att/data/user_de/0/com.miui.aod/app_themes/2023_2_19_11824_478371246.aodBackup",
    "apps/com.miui.aod/miui_att/data/user_de/0/com.miui.aod/app_themes/2023_2_19_11845_1090474991.aodBackup",
    "apps/com.miui.aod/miui_att/data/user_de/0/com.miui.aod/app_themes/2023_2_19_1197_525141537.aodBackup",
    "apps/com.miui.aod/miui_att/data/user_de/0/com.miui.aod/app_themes/2023_2_19_11925_1949457061.aodBackup",
    "apps/com.miui.aod/miui_att/data/user_de/0/com.miui.aod/app_themes/2023_2_19_11944_721739243.aodBackup",
    "apps/com.miui.aod/miui_att/data/user_de/0/com.miui.aod/app_themes/2023_2_19_11107_338674595.aodBackup",
    "apps/com.miui.aod/miui_att/data/user_de/0/com.miui.aod/app_themes/2023_2_19_111025_174535602.aodBackup",
    "apps/com.miui.aod/miui_att/data/user_de/0/com.miui.aod/app_themes/2023_2_19_111044_305999220.aodBackup",
    "apps/com.miui.aod/miui_att/data/user_de/0/com.miui.aod/app_themes/2023_2_19_11114_1678855984.aodBackup",
    "apps/com.miui.aod/miui_att/data/user_de/0/com.miui.aod/app_themes/2023_2_19_111130_1815820008.aodBackup",
    "apps/com.miui.aod/miui_att/data/user_de/0/com.miui.aod/app_themes/2023_2_19_11122_372541210.aodBackup",
    "apps/com.miui.aod/miui_att/data/user_de/0/com.miui.aod/app_themes/2023_2_19_111223_615861899.aodBackup",
    "apps/com.miui.aod/miui_att/data/user_de/0/com.miui.aod/app_themes/2023_2_19_111433_1735170307.aodBackup",
    "apps/com.miui.aod/miui_att/data/user_de/0/com.miui.aod/app_themes/2023_2_19_111710_1979152183.aodBackup",
    "apps/com.miui.aod/miui_att/data/user_de/0/com.miui.aod/app_themes/2023_2_19_111826_1810564365.aodBackup",
]

app = Flask(__name__)

# in-memory cache of extracted preview images: {filename: (mtime, base64_str)}
_preview_cache = {}


def cp_a(src, dst):
    """Copy a file using shutil.copy2 - copies content plus metadata
    (mode, mtime/atime), same as 'cp -p'. Kept as a single helper function
    so the rest of the code (and the reasoning in the comments below) didn't
    need to change - only the copy mechanism itself."""
    shutil.copy2(src, dst)


def find_preview_in_zip(zip_path):
    """Read-only peek inside a theme zip to find drawable/preview_aod_0.(png|jpg|jpeg)
    (path may vary, so we match on filename, not exact folder).
    Returns (bytes, mime_type) or None."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        candidates = [n for n in names if n.lower().endswith(PREVIEW_NAMES)]
        if not candidates:
            return None
        # prefer a path that actually contains "drawable/", then prefer png over jpg
        candidates.sort(key=lambda n: (
            0 if "drawable/" in n.lower() else 1,
            0 if n.lower().endswith(".png") else 1,
        ))
        chosen = candidates[0]
        mime = "image/png" if chosen.lower().endswith(".png") else "image/jpeg"
        with zf.open(chosen) as f:
            return f.read(), mime


def list_theme_files():
    if not os.path.isdir(THEMES_DIR):
        return []
    files = [f for f in os.listdir(THEMES_DIR) if f.lower().endswith(THEME_EXTS)]
    files.sort()
    return files


def get_preview_base64(filename):
    path = os.path.join(THEMES_DIR, filename)
    mtime = os.path.getmtime(path)
    cached = _preview_cache.get(filename)
    if cached and cached[0] == mtime:
        return cached[1]

    try:
        found = find_preview_in_zip(path)
    except Exception:
        # Any corruption or unexpected structure in this one theme file
        # should just mean "no preview available" - it must never take
        # down the whole /api/themes response for every other theme.
        found = None

    if found:
        raw, mime = found
        result = {"data": base64.b64encode(raw).decode("ascii"), "mime": mime}
    else:
        result = None

    _preview_cache[filename] = (mtime, result)
    return result


# ---------------------------------------------------------------------------
# Remote themes library: manifest fetch/cache, on-demand file download.
#
# themes_manifest.json (hosted on GitHub, fetched over plain HTTPS - no API,
# no auth) lists every remotely-available theme with its preview image
# inline, so the grid can show them without downloading the actual
# .aodbackup file. The real file is only downloaded - from a GitHub Release
# asset - the moment it's actually needed to build a backup, and is cached
# afterwards so re-selecting it later doesn't re-download it.
# ---------------------------------------------------------------------------

_manifest_memory = None  # last-known manifest, kept in memory for this run


def _http_get_json(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": "aod-theme-manager"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_manifest_from_disk():
    if not os.path.exists(MANIFEST_CACHE_PATH):
        return None
    try:
        with open(MANIFEST_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_manifest_to_disk(manifest):
    os.makedirs(REMOTE_CACHE_DIR, exist_ok=True)
    with open(MANIFEST_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f)


def fetch_remote_manifest():
    """Actually hits the network. Returns (manifest, error_message) - exactly
    one of the two is None. On success, updates both the in-memory and
    on-disk caches."""
    global _manifest_memory
    if not REMOTE_ENABLED:
        return None, "The remote themes library isn't configured yet (see GITHUB_OWNER in app.py)."
    try:
        manifest = _http_get_json(MANIFEST_URL)
    except Exception as e:
        return None, f"Couldn't reach the themes library ({type(e).__name__})."
    _manifest_memory = manifest
    save_manifest_to_disk(manifest)
    return manifest, None


def get_manifest():
    """Cache-only, no network call - used anywhere that needs to be fast
    (page load) or where a stale-but-cached view is perfectly fine. The
    actual network refresh happens only via /api/themes/refresh, called
    automatically once on page load and by the manual Refresh button."""
    global _manifest_memory
    if _manifest_memory:
        return _manifest_memory
    disk = load_manifest_from_disk()
    if disk:
        _manifest_memory = disk
        return disk
    return {"version": None, "updated": None, "themes": []}


def find_manifest_entry(filename):
    for t in get_manifest().get("themes", []):
        if t.get("filename") == filename:
            return t
    return None


def theme_id_to_source_and_filename(theme_id):
    """Card ids from the frontend are either a plain filename (a locally
    uploaded theme, in themes/) or 'remote:<filename>' (a GitHub-hosted
    theme that may still need downloading)."""
    if theme_id.startswith("remote:"):
        return "remote", theme_id[len("remote:"):]
    return "local", theme_id


def ensure_remote_theme_downloaded(filename):
    """Downloads filename from the GitHub Release into REMOTE_THEMES_DIR if
    it isn't already cached there (or if the cached copy's size doesn't
    match what the manifest expects). Returns the local path, or raises
    RuntimeError with a message safe to show the user."""
    os.makedirs(REMOTE_THEMES_DIR, exist_ok=True)
    dest = os.path.join(REMOTE_THEMES_DIR, filename)
    entry = find_manifest_entry(filename)
    expected_size = entry.get("size_bytes") if entry else None
    expected_sha = entry.get("sha256") if entry else None

    if os.path.exists(dest):
        if expected_size is None or os.path.getsize(dest) == expected_size:
            return dest
        os.remove(dest)  # stale/incomplete cached copy - re-download below

    if not REMOTE_ENABLED:
        raise RuntimeError(
            "This theme lives on GitHub, but the remote themes library isn't configured yet."
        )

    url = f"{RELEASE_ASSET_BASE}/{urllib.parse.quote(filename)}"
    tmp_dest = dest + ".part"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "aod-theme-manager"})
        with urllib.request.urlopen(req, timeout=30) as resp, open(tmp_dest, "wb") as out:
            shutil.copyfileobj(resp, out)
    except Exception as e:
        if os.path.exists(tmp_dest):
            os.remove(tmp_dest)
        raise RuntimeError(f"Couldn't download '{filename}' from GitHub ({type(e).__name__}).") from e

    if expected_sha:
        h = hashlib.sha256()
        with open(tmp_dest, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        if h.hexdigest() != expected_sha:
            os.remove(tmp_dest)
            raise RuntimeError(f"Downloaded '{filename}' doesn't match the expected checksum - try again.")

    os.replace(tmp_dest, dest)
    return dest


def resolve_theme_path(theme_id):
    """Turns a selection id (local filename or 'remote:filename') into an
    actual local file path, downloading it first if needed."""
    source, filename = theme_id_to_source_and_filename(theme_id)
    if source == "local":
        path = os.path.join(THEMES_DIR, filename)
        if not os.path.exists(path):
            raise RuntimeError(f"Local theme file not found: {filename}")
        return path
    return ensure_remote_theme_downloaded(filename)


def _parse_version(v):
    try:
        return tuple(int(p) for p in str(v).strip().lstrip("v").split("."))
    except Exception:
        return None


def is_newer_version(latest, current):
    lp, cp = _parse_version(latest), _parse_version(current)
    if lp is None or cp is None:
        return latest != current
    return lp > cp


MAX_UPLOAD_FILES = 15
REQUIRED_TOP_LEVEL = {"drawable", "content", "aod_description.xml"}
REQUIRED_DRAWABLE_IMAGES = {"preview_aod_small_0.jpg", "preview_aod_0.jpg"}


def validate_theme_zip(path):
    """Returns (ok: bool, message: str). Messages are written for someone
    who isn't looking at the code - they explain what's wrong and why,
    not just which check failed."""
    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()
    except zipfile.BadZipFile:
        return False, (
            "This isn't a valid zip file, so it can't be a theme "
            "- .aodbackup files are zip archives internally."
        )
    except Exception:
        return False, (
            "This file's zip data looks corrupted and can't be read "
            "- try re-exporting or re-creating the .aodbackup file."
        )

    if not names:
        return False, "This archive is empty - there's nothing inside it."

    # First 3 distinct top-level folders/files encountered, in order of
    # first appearance - nothing else may come before them.
    seen = []
    for n in names:
        top = n.split("/")[0]
        if top and top not in seen:
            seen.append(top)
        if len(seen) >= 3:
            break

    if set(seen) != REQUIRED_TOP_LEVEL:
        missing = sorted(REQUIRED_TOP_LEVEL - set(seen))
        unexpected = [s for s in seen if s not in REQUIRED_TOP_LEVEL]
        detail_bits = []
        if missing:
            detail_bits.append(f"missing {', '.join(missing)}")
        if unexpected:
            detail_bits.append(f"found {', '.join(unexpected)} instead")
        detail = "; ".join(detail_bits) if detail_bits else f"found {', '.join(seen) or 'nothing'}"
        return False, (
            f"Doesn't match the expected theme layout. The first things in the zip "
            f"must be drawable/, content/ and aod_description.xml ({detail})."
        )

    drawable_files = {n.split("/")[-1] for n in names if n.startswith("drawable/")}
    missing = REQUIRED_DRAWABLE_IMAGES - drawable_files
    if missing:
        return False, (
            f"The drawable/ folder is missing {', '.join(sorted(missing))}, "
            f"so there'd be no preview image to show in the picker."
        )

    return True, "OK"


def unique_theme_path(filename):
    """Avoids clobbering an existing theme with the same name."""
    base, ext = os.path.splitext(filename)
    candidate = filename
    i = 1
    while os.path.exists(os.path.join(THEMES_DIR, candidate)):
        candidate = f"{base}_{i}{ext}"
        i += 1
    return os.path.join(THEMES_DIR, candidate), os.path.basename(candidate)


@app.route("/api/upload", methods=["POST"])
def api_upload():
    files = request.files.getlist("files")

    if not files:
        return jsonify({"error": "No files received."}), 400
    if len(files) > MAX_UPLOAD_FILES:
        return jsonify({"error": f"You can upload at most {MAX_UPLOAD_FILES} files at once."}), 400

    os.makedirs(THEMES_DIR, exist_ok=True)
    results = []

    for f in files:
        original_name = f.filename or "unnamed"

        if not original_name.lower().endswith(".aodbackup"):
            results.append({"filename": original_name, "status": "rejected",
                             "reason": "This needs a .aodbackup extension - that file looks like a different type."})
            continue

        tmp_path = os.path.join(THEMES_DIR, f".__upload_tmp_{os.getpid()}_{len(results)}.aodbackup")
        f.save(tmp_path)

        ok, message = validate_theme_zip(tmp_path)
        if not ok:
            os.remove(tmp_path)
            results.append({"filename": original_name, "status": "rejected", "reason": message})
            continue

        final_path, final_name = unique_theme_path(original_name)
        os.replace(tmp_path, final_path)
        results.append({"filename": final_name, "status": "added", "reason": "OK"})

    return jsonify({"results": results})


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/themes")
def api_themes():
    """Fast and cache-only - never blocks on a network call. The grid is
    the union of locally uploaded themes (themes/, unchanged from before)
    and whatever's in the last-fetched remote manifest. Remote entries
    carry their preview inline but have no local file yet - that's only
    downloaded when the theme is actually used to generate a backup."""
    result = []

    for fname in list_theme_files():
        try:
            preview = get_preview_base64(fname)  # {"data": ..., "mime": ...} or None
        except Exception:
            # Defense in depth: a single unreadable theme file must never
            # break the grid for every other theme.
            preview = None
        result.append({
            "id": fname,
            "filename": fname,
            "name": os.path.splitext(fname)[0],
            "preview": preview["data"] if preview else None,
            "preview_mime": preview["mime"] if preview else None,
            "source": "local",
        })

    manifest = get_manifest()
    for entry in manifest.get("themes", []):
        fname = entry.get("filename")
        if not fname:
            continue
        result.append({
            "id": f"remote:{fname}",
            "filename": fname,
            "name": entry.get("name") or os.path.splitext(fname)[0],
            "preview": entry.get("preview"),
            "preview_mime": entry.get("preview_mime", "image/jpeg"),
            "source": "remote",
        })

    return jsonify({
        "themes": result,
        "manifest_version": manifest.get("version"),
        "manifest_updated": manifest.get("updated"),
        "remote_enabled": REMOTE_ENABLED,
    })


@app.route("/api/themes/refresh", methods=["POST"])
def api_themes_refresh():
    """The actual network hit: re-fetches themes_manifest.json from GitHub.
    Called automatically once right after the page loads, and by the
    manual Refresh button - never by /api/themes itself, so page load
    always stays instant even on a slow or absent connection."""
    manifest, err = fetch_remote_manifest()
    if err:
        return jsonify({"ok": False, "error": err}), 502
    return jsonify({
        "ok": True,
        "version": manifest.get("version"),
        "updated": manifest.get("updated"),
        "theme_count": len(manifest.get("themes", [])),
    })


@app.route("/api/app-version")
def api_app_version():
    """Checks version.json on GitHub against CURRENT_APP_VERSION. Never
    downloads or replaces anything - just tells the frontend whether to
    show an 'update available' banner with a link to the release."""
    if not REMOTE_ENABLED:
        return jsonify({"current": CURRENT_APP_VERSION, "update_available": False, "checked": False})
    try:
        info = _http_get_json(APP_VERSION_URL, timeout=6)
    except Exception:
        return jsonify({"current": CURRENT_APP_VERSION, "update_available": False, "checked": False})

    latest = info.get("version")
    release_url = info.get("release_url") or f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases"
    return jsonify({
        "current": CURRENT_APP_VERSION,
        "latest": latest,
        "update_available": bool(latest) and is_newer_version(latest, CURRENT_APP_VERSION),
        "release_url": release_url,
        "checked": True,
    })


def get_target_slots():
    """Returns the sorted list of existing filenames in the pristine apps
    folder's app_themes directory (the 26 original theme zips)."""
    target_dir = os.path.join(ORIGINAL_SOURCE_DIR, APP_THEMES_REL)
    if not os.path.isdir(target_dir):
        return []
    files = [f for f in os.listdir(target_dir) if f.lower().endswith(THEME_EXTS)]
    files.sort()
    return files


@app.route("/api/slots")
def api_slots():
    slots = get_target_slots()
    return jsonify({
        "total_slots": len(slots),
        "replaceable_slots": slots[:FIRST_N],
        "untouched_slots": slots[FIRST_N:],
    })


def ensure_work_dir_exists():
    """One-time setup: copy original_source -> work ONLY if work doesn't
    already exist. After this, work/apps is a persistent folder that is
    edited in place forever after - never deleted and rebuilt - so its
    internal directory ordering, inode identity, and every untouched file's
    original timestamps stay exactly as they were on the very first copy,
    the same way MT Manager editing the original folder in place would."""
    if not os.path.exists(WORK_DIR):
        shutil.copytree(ORIGINAL_SOURCE_DIR, WORK_DIR)


def ensure_pristine_slots_saved(replaceable_slots):
    """Snapshot the ORIGINAL bytes of the 20 replaceable slot files, taken
    once from original_source, so every future generation can restore a
    slot to its untouched state before applying a new theme - without ever
    deleting/recreating the slot file itself."""
    os.makedirs(PRISTINE_SLOTS_DIR, exist_ok=True)
    source_target_dir = os.path.join(ORIGINAL_SOURCE_DIR, APP_THEMES_REL)
    for slot_filename in replaceable_slots:
        snapshot_path = os.path.join(PRISTINE_SLOTS_DIR, slot_filename)
        if not os.path.exists(snapshot_path):
            cp_a(os.path.join(source_target_dir, slot_filename), snapshot_path)


def build_backup(selected_filenames):
    """selected_filenames: ordered list of theme ids (a plain filename for
    a local/uploaded theme, or 'remote:filename' for a GitHub-hosted one),
    length <= FIRST_N. Returns path to the produced .bak file.

    Critically: work/apps is never deleted and rebuilt. Every generation
    only overwrites the CONTENTS of the same 20 existing files in place -
    same directory entries, same inodes, same untouched neighbors - which
    mirrors exactly what a manual MT Manager edit does."""

    if len(selected_filenames) > FIRST_N:
        raise ValueError(f"Cannot select more than {FIRST_N} themes.")

    slots = get_target_slots()
    if len(slots) < FIRST_N:
        raise RuntimeError(
            f"Expected at least {FIRST_N} theme slots in original_source, found {len(slots)}."
        )
    replaceable = slots[:FIRST_N]

    ensure_work_dir_exists()
    ensure_pristine_slots_saved(replaceable)

    target_dir = os.path.join(WORK_DIR, APP_THEMES_REL)

    # 1. Reset all 20 replaceable slots back to their pristine originals,
    #    in place (overwrite existing file content, same inode - no delete).
    for slot_filename in replaceable:
        snapshot_path = os.path.join(PRISTINE_SLOTS_DIR, slot_filename)
        dst = os.path.join(target_dir, slot_filename)
        cp_a(snapshot_path, dst)

    # 2. Apply this generation's selections, in place. Uses 'cp -a' (real OS
    #    copy) instead of shutil, per the theory that Python's own copy
    #    implementation differs subtly from a native file-manager copy.
    #    resolve_theme_path downloads remote-sourced selections on demand
    #    (cached after the first time) before handing back a local path.
    for slot_filename, theme_id in zip(replaceable, selected_filenames):
        src = resolve_theme_path(theme_id)
        dst = os.path.join(target_dir, slot_filename)  # keep ORIGINAL slot name
        cp_a(src, dst)

    # 3. Compress using the exact same header/tar logic as compress1.py
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, "custom_aod_backup.bak")
    apps_folder = os.path.join(WORK_DIR, "apps")
    create_final_validated_backup(apps_folder, output_path)
    return output_path


def create_final_validated_backup(source_folder, output_filename):
    """Same header/USTAR settings as compress1.py, but writes tar members in
    the exact order confirmed to restore correctly on HyperOS (see
    CANONICAL_MEMBER_ORDER). A fresh os.walk() on a freshly-copied folder is
    NOT guaranteed to return entries in the original order, and HyperOS's
    restore turned out to be order-sensitive - hence the fixed order here."""
    header_text = (
        "MIUI BACKUP\n2\ncom.miui.aod Always-on display\n-1\n0\n"
        "ANDROID BACKUP\n5\n0\nnone\n"
    ).encode("utf-8")

    parent_dir = os.path.dirname(source_folder)

    # Build ordered list of (full_path, arcname): canonical entries first (in
    # their known-good order), then anything else found on disk that wasn't
    # in the canonical list (so the tool doesn't silently drop new/unexpected
    # files), sorted for determinism.
    all_files = {}
    for root, dirs, files in os.walk(source_folder):
        for file in files:
            full_path = os.path.join(root, file)
            arcname = os.path.relpath(full_path, start=parent_dir).replace(os.sep, "/")
            all_files[arcname] = full_path

    ordered = []
    for arcname in CANONICAL_MEMBER_ORDER:
        if arcname in all_files:
            ordered.append((all_files.pop(arcname), arcname))
    # anything left over (not part of the canonical list) goes last, sorted
    for arcname in sorted(all_files):
        ordered.append((all_files[arcname], arcname))

    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for full_path, arcname in ordered:
            info = tar.gettarinfo(full_path, arcname=arcname)
            info.uid = 1000
            info.gid = 1000
            info.uname = ""
            info.gname = ""
            with open(full_path, "rb") as f:
                tar.addfile(info, f)

    with open(output_filename, "wb") as out_file:
        out_file.write(header_text)
        out_file.write(tar_stream.getvalue())


@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json(force=True)
    selected = data.get("selected", [])

    if not selected:
        return jsonify({"error": "No themes selected."}), 400
    if len(selected) > FIRST_N:
        return jsonify({"error": f"Select at most {FIRST_N} themes."}), 400

    local_available = set(list_theme_files())
    remote_available = {f"remote:{t['filename']}" for t in get_manifest().get("themes", []) if t.get("filename")}
    unknown = [tid for tid in selected if tid not in local_available and tid not in remote_available]
    if unknown:
        return jsonify({"error": f"Unknown theme(s): {unknown}"}), 400

    try:
        output_path = build_backup(selected)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"ok": True, "download": "/api/download"})


@app.route("/api/download")
def api_download():
    output_path = os.path.join(OUTPUT_DIR, "custom_aod_backup.bak")
    if not os.path.exists(output_path):
        return jsonify({"error": "No backup generated yet."}), 404
    return send_file(output_path, as_attachment=True, download_name="custom_aod_backup.bak")


if __name__ == "__main__":
    os.makedirs(THEMES_DIR, exist_ok=True)
    os.makedirs(ORIGINAL_SOURCE_DIR, exist_ok=True)
    print(f"Themes folder:   {THEMES_DIR}")
    print(f"Original source: {ORIGINAL_SOURCE_DIR}  (must contain an 'apps' folder)")
    app.run(host="127.0.0.1", port=5000, debug=True)
