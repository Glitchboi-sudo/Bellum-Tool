#!/usr/bin/env bash
# Stage a self-contained install tree of Bellum Tool (app + PySide6 bundled)
# into $1, ready to be turned into a .deb / .rpm by fpm.
#
# Usage:  packaging/stage-bundle.sh <stage-dir> <wheel-file>
#
# Layout produced:
#   <stage>/opt/bellum-tool/           <- app package + vendored deps (PySide6)
#   <stage>/usr/bin/bellum-tool        <- launcher
#   <stage>/usr/share/applications/... <- .desktop
#   <stage>/usr/share/icons/...        <- scalable icon
set -euo pipefail

STAGE="${1:?stage dir required}"
WHEEL="${2:?wheel file required}"
HERE="$(cd "$(dirname "$0")" && pwd)"

rm -rf "$STAGE"
mkdir -p "$STAGE/opt/bellum-tool" "$STAGE/usr/bin"

# Vendored install: app + all runtime deps (PySide6) under /opt so the package
# is self-contained and does not depend on each distro's PySide6 packaging.
python3 -m pip install --no-compile --target "$STAGE/opt/bellum-tool" "$WHEEL"

# Launcher
cat > "$STAGE/usr/bin/bellum-tool" <<'EOF'
#!/bin/sh
export PYTHONPATH="/opt/bellum-tool${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m bellum "$@"
EOF
chmod 0755 "$STAGE/usr/bin/bellum-tool"

# Desktop entry + icon
install -Dm644 "$HERE/bellum-tool.desktop" \
    "$STAGE/usr/share/applications/bellum-tool.desktop"
install -Dm644 "$HERE/bellum-tool.svg" \
    "$STAGE/usr/share/icons/hicolor/scalable/apps/bellum-tool.svg"
install -Dm644 "$HERE/../LICENSE" \
    "$STAGE/usr/share/doc/bellum-tool/copyright"

echo "Staged bundle at: $STAGE"
