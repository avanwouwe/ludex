#!/usr/bin/env bash
# Build the Ludex agent.
#
# Prerequisites (one-time):
#   agent/.venv/bin/pip install -e '.[build]'
#
# macOS  → dist/Ludex.app   (via ludex.spec, which adds the BUNDLE step and LSUIElement)
# Linux  → dist/ludex        (single-file binary via --onefile)
#
# Run on each target OS — PyInstaller does not cross-compile.
# The resulting binary/bundle bundles Python + psutil/requests/yaml;
# no Python runtime is needed on the endpoint.  Run `./ludex install` (Linux)
# or double-click / right-click → Open (macOS) to install.
set -euo pipefail

cd "$(dirname "$0")/.."   # -> agent/

PYINSTALLER="./.venv/bin/pyinstaller"
[ -x "$PYINSTALLER" ] || PYINSTALLER="pyinstaller"

if [[ "$(uname)" == "Darwin" ]]; then
  # Use the spec file so the BUNDLE step and Info.plist are applied correctly.
  # ludex-mac.spec is version-controlled; ludex.spec is gitignored (Linux auto-generates it).
  "$PYINSTALLER" --clean --noconfirm ludex-mac.spec
  echo
  echo "Built: $(pwd)/dist/Ludex.app"
else
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
fi
