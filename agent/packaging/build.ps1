# Build the Ludex agent as a single self-contained binary for Windows.
#
#   agent\.venv\Scripts\pip install -e ".[build]"   # one-time: installs pyinstaller
#   agent\packaging\build.ps1                        # produces agent\dist\ludex.exe
#
# Run on a Windows machine — PyInstaller does not cross-compile.
# The resulting binary bundles Python + psutil/requests/yaml, so no Python
# runtime is needed on the endpoint. It is its own installer: .\ludex.exe install

$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

$pyinstaller = ".\.venv\Scripts\pyinstaller.exe"
if (-not (Test-Path $pyinstaller)) { $pyinstaller = "pyinstaller" }

& $pyinstaller `
  --onefile `
  --clean `
  --noconfirm `
  --name ludex `
  --paths . `
  --hidden-import ludex.platform.linux `
  --hidden-import ludex.platform.darwin `
  --hidden-import ludex.platform.windows `
  packaging\ludex_entry.py

Write-Host ""
Write-Host "Built: $(Get-Location)\dist\ludex.exe"
