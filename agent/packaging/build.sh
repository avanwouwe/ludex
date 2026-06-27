#!/usr/bin/env bash
# Build the Ludex agent as a single self-contained binary.
#
#   agent/.venv/bin/pip install -e '.[build]'   # one-time: installs pyinstaller
#   agent/packaging/build.sh                     # produces agent/dist/ludex
#
# Run on each target OS to produce that platform's binary (PyInstaller does not
# cross-compile). The resulting binary bundles Python + psutil/requests/yaml, so the
# endpoint needs no Python runtime. It is its own installer: `./ludex install`.
set -euo pipefail

cd "$(dirname "$0")/.."   # -> agent/

# Prefer the venv's pyinstaller if present, else whatever is on PATH.
PYINSTALLER="./.venv/bin/pyinstaller"
[ -x "$PYINSTALLER" ] || PYINSTALLER="pyinstaller"

"$PYINSTALLER" \
  --onefile \
  --clean \
  --noconfirm \
  --name ludex \
  --paths . \
  --hidden-import ludex.platform.linux \
  --hidden-import ludex.platform.darwin \
  packaging/ludex_entry.py

echo
echo "Built: $(pwd)/dist/ludex"
