#companion.py
# FLX.AI Windows Companion

This repository builds the **local Windows companion** used by the FLX.AI website. It is separate from the Render website repository.

## Repository contents

```text
.
├── companion.py
├── companion-requirements.txt
├── README.md
├── .gitignore
└── .github/
    └── workflows/
        └── build-windows-exe.yml
```

## Create the new GitHub repository

1. Create a new repository named `flx-ai-windows-companion` (or another name you prefer).
2. Choose **Public** or **Private** as you prefer. GitHub Actions works with either, subject to your account's Actions limits.
3. Do not add a README, `.gitignore`, or license during repository creation if you are uploading these files as a complete set.
4. Upload the **contents** of this folder to the repository root. In particular, `.github/workflows/build-windows-exe.yml` must be at exactly that path. Do not upload the outer folder as an extra nested directory.
5. Commit the files to the `main` branch.

## Build and download the EXE

1. Open the repository's **Actions** tab.
2. Select **Build FLX.AI Windows Companion**.
3. Wait for the newest run on `main` to finish with a green check.
4. Open that exact successful run.
5. In its **Artifacts** section, download the artifact whose name starts with `FLXAI-Companion-Windows-run-` and has that run's number.
6. Extract the downloaded ZIP. It contains `FLXAI-Companion.exe`.

Every run gets a distinct artifact name, making it easier to distinguish the latest build from earlier builds. A re-run builds the commit attached to that run; it does not include uncommitted or later commits.

## Run on Windows

1. Close any older FLX.AI companion instance first.
2. Run the newly extracted `FLXAI-Companion.exe` on the same Windows PC as the browser using FLX.AI.
3. Keep it running while using Local Mode.
4. Visit `http://127.0.0.1:8765/health` on that PC. A healthy companion reports `ok: true` and version `4.0`.
5. Open `https://flx-ai-demo.onrender.com` and test Local Mode.

The companion binds to `127.0.0.1:8765` only. It does not expose the Windows control endpoint to the public internet.

## Updating the companion

Edit the existing `companion.py` in this repository (do not upload a second copy with a different filename). Commit the change to `main`. The push automatically starts a new build because the workflow watches `companion.py`, `companion-requirements.txt`, and its own workflow file. Download the artifact from the newly completed run.

If dependencies change, update `companion-requirements.txt` too. Changes to unrelated files do not trigger an automatic build; use **Actions → Build FLX.AI Windows Companion → Run workflow** when you intentionally need a manual rebuild.

## Architecture

- Render website: `app.py`, `templates/index.html`, Gemini API integration.
- This repository: `companion.py` packaged as a Windows `.exe`.
- The browser's Local Mode sends actions to the companion running on the same PC at `127.0.0.1:8765`.
- Gemini chat remains a website feature; this companion does not host the Gemini API key.

## Windows limitations

Some actions depend on the PC, Windows edition, hardware, installed applications, device drivers, and permissions. Wi-Fi/Bluetooth changes may require administrator permissions. Brightness may not be controllable on external monitors. Media-key events are sent to Windows but cannot guarantee that a media app begins playback. Do not assume an action succeeded unless the companion returns a successful result.
