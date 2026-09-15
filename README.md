<!-- Language selector -->
**English** · [Español](README.es.md) · [Português](README.pt.md)

# Bellum Tool

A native Linux desktop app (Qt6 / PySide6) to manage **PAX PayDroid** point-of-sale
terminals (A910 / A920 / A930, D-series…) over ADB. It is a clean, modern front-end
over [`pax_adb`](https://github.com/Glitchboi-sudo) — AOSP `adb` extended with PAX's
`A_HDSK` handshake and its six proprietary commands (`syslog`, `systool`, `puk`,
`sysver`, `unlink`, `getappinfo`) — plus `fastboot` / `paydroidboot`. It fills the
same role as the Windows *PayDroid Tool*, but as a native desktop application.

> **Neutral device management on hardware you own.** Bellum ships no firmware, no
> bundled APKs, and no "tamper-removal" or payment-security-bypass macros. Critical
> PAX security/payment packages are flagged and gated behind reinforced
> confirmation. See the [Scope & responsible use](#scope--responsible-use) section.

📖 **Full documentation lives in the [Wiki](https://github.com/Glitchboi-sudo/Bellum-Tool/wiki).**

## Features

The sidebar has **5 sections**; related tools are grouped into tabs.

- **Overview** — terminal detection, online/unauthorized/offline status, `getprop`
  property sheet, system status (battery, `/data` storage, resolution, uptime),
  report export (`.json` / `.txt`), normal / bootloader reboot, and wireless ADB
  (Wi-Fi `tcpip` + `connect`).
- **Applications** — generic package manager: list (all/user/system/disabled) with
  version, filter, install APK (or folder), extract/back up APK, uninstall, enable/
  disable, clear data, launch / force-stop, and a per-app detail dialog (info +
  permissions with grant/revoke).
- **Files** — remote browser with push/pull transfer and delete (`unlink`).
- **Diagnostics** — tabs for *Logs* (Android `logcat` or PAX `syslog`), *Console*
  (`adb shell` runner with history), *Capture* (`screencap` viewer), and *Tools*
  (`screenrecord`, `bugreport`, `dumpsys` explorer).
- **Maintenance** — tabs for *Flashing* (`fastboot` front-end with saveable batch
  recipes — **you supply your own images**), *Recycle* (standard wipe: `userdata` /
  `cache` / reboot), and *PAX System* (proprietary `systool`, `puk`, `sysver`,
  `getappinfo`).

## Requirements

- Python 3.10+
- `PySide6` (`pip install -r requirements.txt`)
- The **`pax_adb`** binary (auto-detected; see the Wiki)
- Optional for flashing: `fastboot` (`android-tools`) or `paydroidboot`

## Install

### Packages (recommended)

Grab a package for your distro from the
[Releases](https://github.com/Glitchboi-sudo/Bellum-Tool/releases) page:

| Distro family | Package |
|---|---|
| Debian / Ubuntu / Mint / Pop!_OS | `.deb` |
| Fedora / RHEL / openSUSE | `.rpm` |
| Arch / Manjaro / EndeavourOS | `.pkg.tar.zst` (or the `packaging/PKGBUILD`) |
| Anything else | `.AppImage` (self-contained) |

### From source

```sh
git clone https://github.com/Glitchboi-sudo/Bellum-Tool.git
cd Bellum-Tool
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
./run.sh
```

`run.sh` uses `.venv` automatically and falls back to system `python3`.

## Scope & responsible use

Bellum Tool is a device-management front-end for terminals **you own or are
authorized to service**. It deliberately does **not** include anything that
circumvents PAX payment security or tamper protection. Packages such as
`com.pax.ipp.neptune` and `com.pax.daemon` are highlighted in red and require
reinforced confirmation before any action. Use it lawfully and only on your own
equipment.

## License

Released under the **[GNU General Public License v3.0 or later](LICENSE)** (GPL-3.0-or-later).
