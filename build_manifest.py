"""
Generates themes_manifest.json either from a local folder OR directly
from the 'themes' release tag on GitHub.

Local Usage:
    python build_manifest.py /path/to/your/theme/library

GitHub Actions Usage (automatically downloads release assets):
    python build_manifest.py --remote
"""
import os
import sys
import json
import base64
import zipfile
import hashlib
import tempfile
import urllib.request
from datetime import date, timezone, datetime

PREVIEW_NAMES = ("preview_aod_0.png", "preview_aod_0.jpg", "preview_aod_0.jpeg")

# Repository Configuration
REPO_OWNER = "haadi76"
REPO_NAME = "AOD-Generator"
TARGET_RELEASE_TAG = "themes"


def find_preview(zip_path):
    """Extracts preview image from within the .aodbackup zip file."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        candidates = [n for n in names if n.lower().endswith(PREVIEW_NAMES)]
        if not candidates:
            return None
        candidates.sort(key=lambda n: (
            0 if "drawable/" in n.lower() else 1,
            0 if n.lower().endswith(".png") else 1,
        ))
        chosen = candidates[0]
        mime = "image/png" if chosen.lower().endswith(".png") else "image/jpeg"
        with zf.open(chosen) as f:
            return f.read(), mime


def process_file_info(file_path):
    """Calculates file size and SHA256 hash in 64KB chunks to handle 300MB+ files smoothly."""
    size_bytes = os.path.getsize(file_path)
    sha256_hash = hashlib.sha256()

    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256_hash.update(chunk)

    return size_bytes, sha256_hash.hexdigest()


def fetch_release_assets_to_dir(target_dir):
    """Downloads all .aodbackup files from the 'themes' release tag into target_dir."""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/tags/{TARGET_RELEASE_TAG}"
    req = urllib.request.Request(
        url, 
        headers={"User-Agent": "AOD-Manifest-Builder"}
    )
    
    token = os.getenv("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    print(f"Fetching release metadata from {url}...")
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
    except Exception as e:
        print(f"Error accessing release tag '{TARGET_RELEASE_TAG}': {e}")
        sys.exit(1)

    assets = data.get("assets", [])
    downloaded_files = 0

    for asset in assets:
        fname = asset["name"]
        if fname.lower().endswith(".aodbackup"):
            download_url = asset["browser_download_url"]
            dest_path = os.path.join(target_dir, fname)
            print(f"  Downloading release asset: {fname} ({asset['size']:,} bytes)...")
            
            dl_req = urllib.request.Request(
                download_url, 
                headers={"User-Agent": "AOD-Manifest-Builder"}
            )
            if token:
                dl_req.add_header("Authorization", f"Bearer {token}")

            with urllib.request.urlopen(dl_req) as resp, open(dest_path, "wb") as out_file:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    out_file.write(chunk)
            
            downloaded_files += 1

    if downloaded_files == 0:
        print(f"No .aodbackup assets found in release tag '{TARGET_RELEASE_TAG}'.")
        sys.exit(1)


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--remote":
        temp_dir = tempfile.mkdtemp()
        print(f"Running in remote mode. Fetching assets from release tag '{TARGET_RELEASE_TAG}'...")
        fetch_release_assets_to_dir(temp_dir)
        src_dir = temp_dir
    elif len(sys.argv) == 2:
        src_dir = sys.argv[1]
        if not os.path.isdir(src_dir):
            print(f"Not a folder: {src_dir}")
            sys.exit(1)
    else:
        print("Usage:")
        print("  Local:  python build_manifest.py /path/to/theme/folder")
        print("  Remote: python build_manifest.py --remote")
        sys.exit(1)

    files = sorted(f for f in os.listdir(src_dir) if f.lower().endswith(".aodbackup"))
    if not files:
        print(f"No .aodbackup files found in {src_dir}")
        sys.exit(1)

    themes = []
    skipped = []

    for fname in files:
        path = os.path.join(src_dir, fname)
        try:
            found = find_preview(path)
        except zipfile.BadZipFile:
            skipped.append((fname, "not a valid zip file"))
            continue
        except Exception as e:
            skipped.append((fname, f"{type(e).__name__}: {e}"))
            continue

        if not found:
            skipped.append((fname, "no preview_aod_0.* image found inside drawable/"))
            continue

        raw, mime = found
        size_bytes, sha256_hex = process_file_info(path)

        themes.append({
            "filename": fname,
            "name": os.path.splitext(fname)[0],
            "preview": base64.b64encode(raw).decode("ascii"),
            "preview_mime": mime,
            "size_bytes": size_bytes,
            "sha256": sha256_hex,
        })
        print(f"  processed {fname}  ({size_bytes:,} bytes)")

    manifest = {
        "version": datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"),
        "updated": date.today().isoformat(),
        "themes": themes,
    }

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes_manifest.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nWrote {out_path} with {len(themes)} theme(s).")

    if skipped:
        print(f"\nSkipped {len(skipped)} file(s):")
        for fname, reason in skipped:
            print(f"  - {fname}: {reason}")


if __name__ == "__main__":
    main()