# Beer Festival App — Build Environment Notes

This documents the WSL/Buildozer setup so you can pick back up if your
computer restarts, WSL closes, or you come back to this after a break.

## Contents

- [Day-to-day workflow (after editing code on Windows)](#day-to-day-workflow-after-editing-code-on-windows)
- [Quick resume (if a build was interrupted)](#quick-resume-if-a-build-was-interrupted)
- [One-time environment setup (already done — for reference only)](#one-time-environment-setup-already-done--for-reference-only)
- [Keeping the Linux copy up to date](#keeping-the-linux-copy-up-to-date)
- [Key buildozer.spec settings](#key-buildozerspec-settings)
- [Where the APK ends up](#where-the-apk-ends-up)
- [Known issues hit during setup (for reference)](#known-issues-hit-during-setup-for-reference)
- [Installing via adb (instead of manually copying the APK)](#installing-via-adb-instead-of-manually-copying-the-apk)
- [Useful commands](#useful-commands)

## Day-to-day workflow (after editing code on Windows)

This is the routine for making a change and testing it on your phone:

1. Edit and save your changes in VS Code on Windows as normal, then
   commit and push to GitHub (`git add`, `git commit`, `git push`).
2. In your **Ubuntu (WSL)** terminal:
   ```
   source ~/buildozer-env/bin/activate
   ```
   ```
   cd ~/beer_festival_app
   ```
   ```
   git pull
   ```
   ```
   buildozer -v android debug
   ```
   No need for a full clean (`rm -rf .buildozer`) for ordinary code
   changes — Buildozer only rebuilds what changed, so this is usually
   fast. A full clean is only needed after changing `buildozer.spec`
   settings like the Python version or NDK pin.
3. Once it says `BUILD SUCCESSFUL`, install the updated APK straight
   to your phone via `adb` (phone connected by USB, USB debugging
   enabled — see "Installing via adb" below):
   ```
   cd C:\platform-tools
   .\adb install -r "\\wsl$\Ubuntu\home\jisok\beer_festival_app\bin\beerfestivalapp-0.1-arm64-v8a_armeabi-v7a-debug.apk"
   ```
   The `-r` flag reinstalls over the existing app (keeping it simple —
   no need to uninstall the old version first each time).
4. Watch your phone screen and tap **Install** on the confirmation
   prompt that appears.

## Quick resume (if a build was interrupted)

1. Open **Ubuntu** from the Windows Start menu (WSL persists across
   Windows restarts — nothing here needs reinstalling just because you
   rebooted).
2. Activate the virtual environment:
   ```
   source ~/buildozer-env/bin/activate
   ```
   Your prompt should now show `(buildozer-env)` at the start.
3. Go into the project folder:
   ```
   cd ~/beer_festival_app
   ```
4. Re-run the build:
   ```
   buildozer -v android debug
   ```
   Buildozer caches downloaded SDK/NDK/build artifacts under
   `.buildozer/`, so a resume after an interruption (not a fresh clean)
   should be much faster than a first build.

If it fails partway through with an error you haven't seen before,
paste the error and troubleshoot from there. If you see a familiar
error from the list below, jump to that fix.

## One-time environment setup (already done — for reference only)

These steps were completed already. You shouldn't need to repeat them
unless WSL/Ubuntu itself gets removed or badly corrupted.

1. **Install WSL** (Windows PowerShell, as Administrator):
   ```
   wsl --install
   ```
2. **Install Linux build dependencies** (inside Ubuntu):
   ```
   sudo apt update && sudo apt upgrade -y
   sudo apt install -y python3-pip build-essential git python3-dev ffmpeg \
     libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
     libportmidi-dev libswscale-dev libavformat-dev libavcodec-dev \
     zlib1g-dev unzip openjdk-17-jdk autoconf automake libtool pkg-config \
     libssl-dev
   ```
   > Note: some of these (`libsdl2-dev` and friends) were later found to
   > cause build conflicts and were purged again — see "Known issues"
   > below. If you're setting this up completely from scratch, it may be
   > worth skipping the SDL2/harfbuzz/freetype/glib/webp/opus dev
   > packages entirely, since Buildozer builds its own Android-specific
   > copies anyway.
3. **Install Python 3.11** (needed instead of Ubuntu's default 3.14,
   which is too new for Buildozer's tooling — via the deadsnakes PPA):
   ```
   sudo apt install -y software-properties-common
   sudo add-apt-repository ppa:deadsnakes/ppa
   sudo apt update
   sudo apt install -y python3.11 python3.11-venv
   ```
4. **Create the virtual environment**:
   ```
   python3.11 -m venv ~/buildozer-env
   source ~/buildozer-env/bin/activate
   ```
5. **Install a pinned, known-stable Buildozer version**:
   ```
   pip install buildozer==1.5.0 cython
   ```
6. **Clone the project from GitHub** (rather than copying from Windows):
   ```
   git clone https://github.com/Jisok22/Beer-Festivals-App.git beer_festival_app
   cd beer_festival_app
   ```
   GitHub requires a **Personal Access Token** instead of your normal
   password when prompted for authentication (Settings → Developer
   settings → Personal access tokens on github.com).

## Keeping the Linux copy up to date

Since you edit and commit from Windows/VS Code, sync changes into the
Linux copy before each build:
```
cd ~/beer_festival_app
git pull
```

## Key buildozer.spec settings

These are already saved in `buildozer.spec`, but noted here in case the
file ever needs recreating:

```
title = Beer Festival List
package.name = beerfestivalapp
package.domain = uk.jisok
requirements = python3==3.11.9,hostpython3==3.11.9,kivy
android.ndk = 25b
```

The Python version pins were necessary because newer default versions
(3.14) aren't yet well-supported by Buildozer's Android build tooling.
`hostpython3` and `python3` must always be pinned to the **same**
version, or the build fails immediately with a version-mismatch error.

## Where the APK ends up

Once a build succeeds, the APK appears in:
```
~/beer_festival_app/bin/
```
Copy it to your phone (USB, email, or cloud drive) and install it,
allowing "install from unknown sources" the first time.

## Known issues hit during setup (for reference)

- **`externally-managed-environment` pip error** → fixed by using a
  virtual environment (`python3.11 -m venv`) instead of installing
  packages system-wide.
- **`autoreconf: not found`** → fixed with
  `sudo apt install -y autoconf automake libtool pkg-config`.
- **`__GNUC_PREREQ` / `cdefs.h` compile errors** → caused by host
  SDL2/freetype/harfbuzz/glib/libpng/webp/opus dev packages leaking
  into the Android cross-compile via `pkg-config`. Fixed by purging
  those host dev packages:
  ```
  sudo apt remove --purge libsdl2-dev libsdl2-image-dev \
    libsdl2-mixer-dev libsdl2-ttf-dev libharfbuzz-dev libglib2.0-dev \
    libfreetype-dev libfreetype6-dev libpng-dev libwebp-dev libopus-dev
  ```
- **SSL/pip errors building `hostpython3`** → fixed with
  `sudo apt install -y libssl-dev`.
- **`not a supported wheel on this platform` / pip self-upgrade
  `ImportError`s** → caused by Buildozer defaulting to a too-new
  target Python (3.14.2). Fixed by pinning
  `requirements = python3==3.11.9,hostpython3==3.11.9,kivy` in
  `buildozer.spec`.
- If a pip-related `ImportError` shows up again during the build, try
  clearing pip's cache first: `rm -rf ~/.cache/pip`, then do a full
  clean (`rm -rf .buildozer bin`) and rebuild.
- **Repeated pip self-upgrade `ImportError`s** (different specific
  missing names each time, e.g. `open_rich_spinner`,
  `BuildDependencyInstallError`, `RequirementInformation`) → pip's own
  self-upgrade step was corrupting itself. Fixed by pinning pip to its
  exact bootstrapped version so the upgrade becomes a no-op:
  ```
  echo 'pip==24.0' > ~/pip-constraints.txt
  mkdir -p ~/.config/pip
  printf '[install]\nconstraint = %s/pip-constraints.txt\n' "$HOME" > ~/.config/pip/pip.conf
  ```
  This is a one-time system-level fix (not project-specific) — should
  already be in place, but worth knowing about if it ever needs
  recreating.
- **`sh.CommandNotFound: zip`** (right at the final packaging step) →
  fixed with `sudo apt install -y zip`.

## Installing via adb (instead of manually copying the APK)

Much faster than transferring the file by hand each time, and gives
proper error messages if something goes wrong.

**One-time setup:**
1. On your phone: Settings → About phone → tap "Build number" 7 times
   to unlock Developer options.
2. Settings → Developer options → enable **USB debugging** and
   disable **Verify apps over USB** (the latter caused an
   `INSTALL_FAILED_VERIFICATION_FAILURE` error during setup, since
   Google can't verify a personal debug build).
3. Download `platform-tools` from
   https://developer.android.com/tools/releases/platform-tools and
   extract to `C:\platform-tools` on Windows (not WSL — USB access is
   simpler from Windows directly).
4. Plug your phone in via USB, set its USB mode to "File Transfer",
   and tap "Allow" on the USB debugging prompt that appears on the
   phone.

**Every time:**
```
cd C:\platform-tools
.\adb devices
```
Confirms the phone is detected, then:
```
.\adb install -r "\\wsl$\Ubuntu\home\jisok\beer_festival_app\bin\beerfestivalapp-0.1-arm64-v8a_armeabi-v7a-debug.apk"
```
Watch your phone screen and tap **Install** on the prompt that
appears — this is the step that produced
`INSTALL_FAILED_USER_RESTRICTED: Install canceled by user` when
missed.

If `adb devices` shows nothing: try a different USB port/cable (a
charge-only cable won't work), and make sure the phone's USB mode is
set to File Transfer, not "Charging only".

## Useful commands

| Purpose | Command |
|---|---|
| Full clean (forces complete re-download) | `rm -rf .buildozer bin` |
| Clean just the SDK/NDK platform cache | `rm -rf .buildozer/android/platform` |
| Clean just Buildozer's own build state | `buildozer android clean` |
| Reactivate the virtual environment | `source ~/buildozer-env/bin/activate` |
| Open the project in VS Code (from WSL) | `code .` |
