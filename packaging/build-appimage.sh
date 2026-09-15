#!/usr/bin/env bash
# Build a self-contained AppImage (bundled Python + PySide6 + Bellum Tool) that
# runs on any reasonably recent x86_64 Linux distro.
#
# Requires:  pip install python-appimage
# Usage:     packaging/build-appimage.sh <wheel-file> [out-dir]
set -euo pipefail

WHEEL="$(readlink -f "${1:?wheel file required}")"
OUT="${2:-$(pwd)}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PYVER="${PYVER:-3.11}"

RECIPE="$(mktemp -d)"
trap 'rm -rf "$RECIPE"' EXIT

# python-appimage "application" recipe: one .desktop, an icon, requirements.txt
cp "$HERE/bellum-tool.desktop" "$RECIPE/bellum-tool.desktop"
cp "$HERE/bellum-tool.svg"     "$RECIPE/bellum-tool.svg"
printf '%s\n' "$WHEEL" > "$RECIPE/requirements.txt"

mkdir -p "$OUT"
( cd "$OUT" && python-appimage build app -p "$PYVER" "$RECIPE" )

echo "AppImage(s) in: $OUT"
ls -1 "$OUT"/*.AppImage
