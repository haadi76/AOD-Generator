"""
Run this locally, pointed at a folder containing your full library of real
.aodbackup theme files, to (re)generate themes_manifest.json - the small
file that tells the website what themes exist on GitHub, complete with
preview images, without the website needing the actual (much larger)
theme files until someone picks one.

    python build_manifest.py /path/to/your/theme/library

This script only READS local files and WRITES themes_manifest.json next to
itself. It never touches GitHub - uploading is a separate manual step
printed at the end.

After running it:
  1. Upload every .aodbackup file in that folder as a Release asset. The
     Release's tag must match RELEASE_TAG in app.py. Easiest with the
     GitHub CLI (https://cli.github.com):
         gh release upload <tag> /path/to/your/theme/library/*.aodbackup
     ...or drag-and-drop them onto the Release's "Assets" section on
     github.com/<owner>/<repo>/releases.
  2. Commit and push the generated themes_manifest.json to your repo, at
     the branch/path app.py's MANIFEST_URL points at (repo root by
     default). Existing users pick it up automatically next time they
     open the app or hit "Refresh" - no re-download of the app itself.

Re-run this any time you add, remove, or replace theme files in your
library folder; it always regenerates the whole manifest from what's
currently in that folder.
"""
import os
import sys
import json
import base64
import zipfile
import hashlib
from datetime import date, timezone, datetime

PREVIEW_NAMES = ("preview_aod_0.png", "preview_aod_0.jpg", "preview_aod_0.jpeg")


def find_preview(zip_path):
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


def main():
    if len(sys.argv) != 2:
        print("Usage: python build_manifest.py /path/to/your/theme/library")
        sys.exit(1)

    src_dir = sys.argv[1]
    if not os.path.isdir(src_dir):
        print(f"Not a folder: {src_dir}")
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
        with open(path, "rb") as f:
            file_bytes = f.read()

        themes.append({
            "filename": fname,
            "name": os.path.splitext(fname)[0],
            "preview": base64.b64encode(raw).decode("ascii"),
            "preview_mime": mime,
            "size_bytes": len(file_bytes),
            "sha256": hashlib.sha256(file_bytes).hexdigest(),
        })
        print(f"  added {fname}  ({len(file_bytes):,} bytes)")

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

    print(
        "\nNext steps:\n"
        f"  1. Upload every .aodbackup file in {src_dir} as a Release asset\n"
        "     (the Release's tag must match RELEASE_TAG in app.py):\n"
        f"         gh release upload <tag> {src_dir}/*.aodbackup\n"
        "     (or drag-and-drop them on the Release's edit page on github.com)\n"
        "  2. Commit and push the generated themes_manifest.json to your repo.\n"
    )


if __name__ == "__main__":
    main()
