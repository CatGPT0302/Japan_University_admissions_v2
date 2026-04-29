# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path


project_root = Path(SPECPATH).parent if Path(SPECPATH).name == "packaging" else Path(SPECPATH)

datas = [
    (str(project_root / "frontend" / "dist"), "frontend/dist"),
    (str(project_root / "prompts"), "prompts"),
    (str(project_root / "data" / "sample_pdf_source_registry.csv"), "data"),
    (str(project_root / "data" / "pdf_source_registry.template.csv"), "data"),
]

hiddenimports = [
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    "pypdfium2",
    "pdfminer.high_level",
    "openpyxl",
    "bs4",
    "PIL",
]

a = Analysis(
    [str(project_root / "local_app.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest",
        "streamlit",
        "watchdog",
        "IPython",
        "jupyter",
    ],
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
    name="v1",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
