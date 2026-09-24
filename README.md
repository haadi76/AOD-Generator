<<<<<<< HEAD
# AOD-Generator
=======
# AOD Theme Manager (HyperOS)

Pick 20 Always-On Display themes from a visual preview grid, and get back a
ready-to-restore `.bak` backup with those themes applied — no manual file
swapping, no MT Manager.

This is a small local website: it runs on your own computer or phone and
opens in your browser. It never uploads anything anywhere.

---

## What's included in this download

```
aod_theme_manager/
  app.py                  <- the app (just run this)
  templates/, static/     <- the web page itself
  themes/                 <- your own uploaded theme files (starts empty)
  original_source/apps/   <- the pristine AOD app data these get inserted into
  remote_cache/           <- auto-created; caches the GitHub themes library
  build_manifest.py       <- maintainer tool, not needed to just use the app
```

`original_source/` is already populated — you don't need to set that up.
The theme picker itself is populated two ways (see "Where themes come from"
below): themes you upload yourself, and — once the maintainer has filled in
a GitHub repo (`GITHUB_OWNER`/`GITHUB_REPO` near the top of `app.py`) — a
shared library of themes hosted on GitHub that the app shows previews for
and downloads on demand.

---

## Where themes come from

Two sources, both shown in the same picker grid:

- **Themes you upload** (the upload button) — stored directly in `themes/`,
  work fully offline, and are yours alone.
- **The shared GitHub themes library** — once the maintainer has published
  one, the app shows previews for these automatically (checked once when
  the app opens, and again any time you tap the refresh button) without
  downloading anything. The real theme file is only downloaded — from
  GitHub, over plain HTTPS — the moment you actually pick it and hit
  **Generate Backup**. It's then cached in `remote_cache/`, so picking the
  same theme again later doesn't re-download it. A small cloud icon on a
  theme's preview means it hasn't been downloaded yet.

If the maintainer hasn't set up a GitHub library yet (or you're offline),
this second source is simply empty — uploading and generating from your own
themes works exactly the same either way.

A small banner appears at the top of the page if a newer version of the app
itself is available — it just links to the release, it doesn't install
anything automatically.

---

## Requirements

- **Python 3.8+**
- The `flask` package (installed in one command below)

---

## Setup — Windows

1. Install Python from [python.org](https://www.python.org/downloads/) if
   you don't already have it. During install, tick **"Add Python to PATH"**.
2. Unzip this folder anywhere (e.g. your Desktop).
3. Open **Command Prompt** or **PowerShell** in that folder (Shift + Right-click
   inside the folder → "Open PowerShell window here", or type `cd` to it).
4. Install Flask:
   ```
   pip install flask
   ```
5. Run the app:
   ```
   python app.py
   ```
6. Open your browser and go to:
   ```
   http://127.0.0.1:5000
   ```
7. Click theme previews to select up to 20, then click **Generate Backup**,
   then **Download backup**. The file lands in the `output/` folder inside
   this project (also linked directly from the download button).

---

## Setup — Android (via Termux)

You'll do this entirely on your phone, no PC needed.

1. Install [Termux](https://f-droid.org/packages/com.termux/) from F-Droid
   (the Play Store version is outdated — use F-Droid).
2. Open Termux and run:
   ```
   pkg update
   pkg install python unzip
   termux-setup-storage
   ```
   Approve the storage permission popup — this lets Termux see your phone's
   normal storage (Downloads, etc.).
3. Move the downloaded zip into your phone's **Downloads** folder if it
   isn't already there, then in Termux:
   ```
   cd ~
   unzip /sdcard/Download/aod_theme_manager.zip
   cd aod_theme_manager
   ```
4. Install Flask:
   ```
   pip install flask
   ```
5. Run the app:
   ```
   python app.py
   ```
6. Open your phone's browser (Chrome, etc.) and go to:
   ```
   http://127.0.0.1:5000
   ```
7. Select up to 20 themes and generate as above. The finished file is saved
   inside Termux's own storage, at `output/custom_aod_backup.bak` — copy it
   out to shared storage so you can restore it via Settings:
   ```
   cp output/custom_aod_backup.bak /sdcard/Download/
   ```

---

## Restoring the backup on your phone

1. Copy the generated `.bak` file onto your phone (Windows users: transfer
   it over USB or however you normally move files across).
2. Open **Settings → Backup & restore** (or wherever your HyperOS version
   keeps local backup restore).
3. Restore from that file.
4. Open the AOD theme picker — your 20 new themes should appear in place of
   the originals.

---

## Notes

- Only the **first 20** theme slots get replaced; the last 6 are left
  untouched.
- Closing the terminal/Termux window stops the app. Just re-run
  `python app.py` to start it again later — your selections aren't saved
  between runs, so you'll re-pick each time.
- Nothing you do is ever uploaded anywhere. The app does make outgoing
  requests to GitHub — to check for new themes/app versions, and to
  download a theme file the moment you select and generate with it — but
  only if a GitHub library has been configured (see below) and you have a
  connection. With no library configured, or no connection, the app works
  entirely offline using your own uploaded themes.

## Troubleshooting

- **"python is not recognized"** (Windows): Python wasn't added to PATH
  during install — reinstall and tick that option, or use `py` instead of
  `python` in the commands above.
- **Page won't load**: make sure the terminal/Termux window is still open
  and showing `Running on http://127.0.0.1:5000` with no errors.
- **Backup doesn't restore correctly**: make sure you're using the
  unmodified `themes/` and `original_source/` folders that came with this
  download — swapping in your own without matching the expected structure
  can break the restore.
- **Remote themes won't download / refresh does nothing**: check that
  you're online, and that the maintainer has actually filled in
  `GITHUB_OWNER`/`GITHUB_REPO` in `app.py` (if those are still the
  placeholder `YOUR_GITHUB_USERNAME`/`YOUR_REPO_NAME`, the remote library
  is intentionally disabled and only your own uploaded themes will show).

---

## For the maintainer: publishing themes and updates

This section is for whoever runs the GitHub repo — not needed just to use
the app.

**One-time setup:**

1. In `app.py`, set `GITHUB_OWNER`, `GITHUB_REPO`, and (optionally)
   `RELEASE_TAG` (defaults to `"themes"`) near the top of the file.
2. Create a GitHub Release with that tag — this is where the actual
   `.aodbackup` files live, as release assets. Release assets aren't
   subject to the same size pressure as regular repo content.
3. Push `version.json` (repo root) with the real `release_url` filled in —
   this powers the "update available" banner.

**Publishing a batch of themes:**

1. Put your real `.aodbackup` files in a folder (anywhere on your machine —
   this is *not* the `themes/` folder that ships in the zip, which is for
   users' own uploads).
2. Run:
   ```
   python build_manifest.py /path/to/that/folder
   ```
   This reads each file, pulls out its preview image, and writes
   `themes_manifest.json` — it does not upload anything itself.
3. Upload every `.aodbackup` file in that folder as an asset on your
   Release (tag must match `RELEASE_TAG`):
   ```
   gh release upload <tag> /path/to/that/folder/*.aodbackup
   ```
   (or drag-and-drop them on the Release's edit page on github.com).
4. Commit and push the generated `themes_manifest.json` to the repo root
   (the branch matching `GITHUB_BRANCH` in `app.py`, `main` by default).

That's it — existing users see the new themes automatically (checked on
app launch, or via the refresh button) without re-downloading the app.
Re-run `build_manifest.py` and repeat steps 3–4 any time you add, remove,
or replace themes in your library folder; it always regenerates the whole
manifest from what's currently there.

**Publishing an app update:** bump `CURRENT_APP_VERSION` in `app.py`,
publish a new zip/release however you already do, and update `version.json`
in the repo to the new version number. Existing users just see a banner
linking to the new release — nothing is downloaded or replaced
automatically.
>>>>>>> 1843144 (Set up remote themes library)
