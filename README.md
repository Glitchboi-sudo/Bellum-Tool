<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset=".github/assets/bellum-logo-type-light.svg">
    <img src=".github/assets/bellum-logo-type-dark.svg" alt="Bellum Tool" width="260">
  </picture>
</p>

<p align="center">
  <strong>Built by Glitchboi</strong><br>
  Native Linux control for PAX PayDroid terminals
</p>

<p align="center">
  <img src="https://img.shields.io/badge/status-BETA-orange" alt="Status" />
  <img src="https://img.shields.io/badge/license-GNU_GPLv3-blue" alt="License" />
  <img src="https://img.shields.io/badge/python-3.10%2B-3776AB" alt="Python" />
  <img src="https://img.shields.io/badge/GUI-Qt6%20%2F%20PySide6-41CD52" alt="Qt6 / PySide6" />
  <img src="https://img.shields.io/badge/platform-Linux-333" alt="Platform" />
</p>

<p align="center">
  <strong>English</strong> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.pt.md">Português</a>
</p>

---

## What is Bellum Tool?

Bellum Tool is a **native Linux desktop app** (Qt6 / PySide6) to manage **PAX
PayDroid** point-of-sale terminals (A910 / A920 / A930, D-series…) over ADB. It is a
clean, modern front-end over [`pax_adb`](https://github.com/Glitchboi-sudo/pax_linux)
plus `fastboot` / `paydroidboot`. It fills the same role as the Windows *PayDroid
Tool*, but as a native desktop application.

The sidebar has **5 sections** grouping **9 tool pages**:

- **Overview** — detection, online/unauthorized/offline status, `getprop` sheet,
  system status (battery, `/data`, resolution, uptime), report export, reboot to
  system/bootloader, and wireless ADB.
- **Applications** — a full package manager: list/filter with versions, install
  APK or folder, extract/back up, uninstall, enable/disable, clear data, launch /
  force-stop, and per-app permissions (grant/revoke).
- **Files** — remote browser with push/pull and delete (`unlink`).
- **Diagnostics** — *Logs* (`logcat` or PAX `syslog`), *Console* (`adb shell`),
  *Capture* (`screencap`), *Tools* (`screenrecord`, `bugreport`, `dumpsys`).
- **Maintenance** — *Flashing* (`fastboot` front-end with saveable batch recipes),
  *Recycle* (standard wipe), *PAX System* (the proprietary commands).

---

## Download (Linux)

Packages are published on
**[Releases](https://github.com/Glitchboi-sudo/Bellum-Tool/releases)** and built
automatically on every push.

The **AppImage** bundles Python + Qt + the whole app — no install required:

```bash
chmod +x Bellum-*-x86_64.AppImage
./Bellum-*-x86_64.AppImage
```

Or grab the native package for your distro:

| Distro family | Package | Install |
|---|---|---|
| Debian · Ubuntu · Mint · Pop!_OS | `.deb` | `sudo apt install ./bellum-tool_*.deb` |
| Fedora · RHEL · CentOS | `.rpm` | `sudo dnf install ./bellum-tool-*.rpm` |
| openSUSE | `.rpm` | `sudo zypper install ./bellum-tool-*.rpm` |
| Arch · Manjaro · EndeavourOS | `.pkg.tar.zst` | `sudo pacman -U ./bellum-tool-*.pkg.tar.zst` |
| Anything else | `.AppImage` | `chmod +x *.AppImage && ./*.AppImage` |

Bellum is a **front-end** — a couple of things must exist on the target (they are
not bundled):

| You need… | Why | Install on the target |
|---|---|---|
| **`pax_adb`** binary | the transport to the terminal (auto-detected) | [`Glitchboi-sudo/pax_linux`](https://github.com/Glitchboi-sudo/pax_linux) |
| **`fastboot`** *(optional)* | only for the flashing module | `android-tools` (or `paydroidboot`) |

---

## Install from source

Requires **Python 3.10+**.

```bash
git clone https://github.com/Glitchboi-sudo/Bellum-Tool.git
cd Bellum-Tool

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
./run.sh
```

`run.sh` uses `.venv` automatically and falls back to system `python3`. On Arch you
can also `sudo pacman -S pyside6` and run `python3 main.py` without a venv.

---

## Usage

```bash
./run.sh                      # launch the GUI
PAX_ADB=/path/to/pax_adb ./run.sh   # point at a specific pax_adb binary
```

`pax_adb` is discovered via the `PAX_ADB` env var → `PATH` → known paths, and the
resolved path is saved to settings. If nothing is found, set it in **Settings**
(there's an **Auto-detect** button). Full details in the
**[Wiki → Configuration](https://github.com/Glitchboi-sudo/Bellum-Tool/wiki/Configuration)**.

---

## Documentation

The full manual lives in the
**[project Wiki](https://github.com/Glitchboi-sudo/Bellum-Tool/wiki)**: installation,
configuration, the complete user guide, the PAX proprietary commands, flashing &
recycle flows, architecture, building & packaging, troubleshooting and contributing.

---

## Architecture

The core is **Qt-light** (services + pure parsers); the UI is separate; every device
command runs **asynchronously** through `QProcess`, so the interface never blocks.

```
bellum/
├── core/     no Qt except QProcess — reusable core
│   ├── adb.py        AdbService — discovery + async execution
│   ├── fastboot.py   FastbootService
│   └── models.py     Device, Package (+ pure parsers)
├── ui/
│   ├── theme.py      palettes + QSS (dark/light), WCAG-AA verified
│   ├── icons.py      system theme icons, recolored on the fly
│   ├── widgets.py    Card, badges, EmptyState, Page, TabPage
│   ├── main_window.py sidebar (5 sections), device selector, banner
│   └── pages/        the 9 tool pages
└── app.py    QApplication bootstrap
```

`TabPage` groups the 9 independent pages into 5 sidebar entries and forwards
lifecycle hooks. More in the
**[Wiki → Architecture](https://github.com/Glitchboi-sudo/Bellum-Tool/wiki/Architecture)**.

---

## Scope & responsible use

Bellum Tool is a device-management front-end for terminals **you own or are
authorized to service**. It deliberately does **not** include anything that
circumvents PAX payment security or tamper protection. Packages such as
`com.pax.ipp.neptune` and `com.pax.daemon` are highlighted in red and require
reinforced confirmation before any action. Use it lawfully and only on your own
equipment. See
**[Wiki → Scope & Responsible Use](https://github.com/Glitchboi-sudo/Bellum-Tool/wiki/Scope-and-Responsible-Use)**.

---

## Credits

Built by **[Glitchboi](https://github.com/Glitchboi-sudo)** — *Security from Mexico,
for everyone*.

Built on `PySide6` / Qt6 and the wider Python ecosystem. Talks to PAX terminals
through `pax_adb` and `fastboot` / `paydroidboot`.

---

## License

Copyright © 2026 **Glitchboi**. Distributed under the **[GNU General Public License
v3.0 or later](LICENSE)** (GPL-3.0-or-later).

---

## Support

If Bellum Tool is useful to you, consider supporting its development:

<p align="center">
  <a href="https://buymeacoffee.com/glitchboi">
    <img src="https://img.shields.io/badge/Buy%20Me%20a%20Coffee-Support-FFDD00?logo=buymeacoffee&logoColor=black" alt="Buy Me a Coffee" height="34" />
  </a>
</p>
