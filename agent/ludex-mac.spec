# -*- mode: python ; coding: utf-8 -*-
# macOS build spec — produces dist/Ludex.app.
# Linux uses CLI flags in build.sh (plain --onefile binary, no BUNDLE step).

a = Analysis(
    ['packaging/ludex_entry.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=['ludex.platform.linux', 'ludex.platform.darwin'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Ludex',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,       # no terminal window; installer uses the browser
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

app = BUNDLE(
    exe,
    name='Ludex.app',
    icon=None,
    bundle_identifier='com.ludex.agent',
    info_plist={
        'CFBundleName': 'Ludex',
        'CFBundleDisplayName': 'Ludex',
        'CFBundleVersion': '1.0',
        'CFBundleShortVersionString': '1.0',
        'LSUIElement': True,        # background agent — no Dock icon
        'NSHighResolutionCapable': True,
    },
)
