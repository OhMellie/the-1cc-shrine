# PyInstaller spec: onefile windowed build of The 1CC Shrine.
# Build with:  pyinstaller 1cc_shrine.spec
# The web/ frontend is bundled and resolved at runtime via sys._MEIPASS
# (see resource_path in app.py). User data stays in %APPDATA%\TouhouTracker.

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=[("web", "web")],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="1CCShrine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
