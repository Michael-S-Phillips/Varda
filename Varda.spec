# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

a = Analysis(
    ['src/varda/main.py'],
    pathex=[],
    binaries=[],
    # GDAL data shipped in rasterio, PROJ data from pyproj, HyPyRameter's parameter
    # tables, Varda's resources and the bundled spectral library
    datas=collect_data_files('rasterio') + collect_data_files('pyproj')
    + collect_data_files('hypyrameter')
    + [('resources', 'resources'), ('librarySpectra', 'librarySpectra')],
    # HyPyRameter's optional denoiser (iovf_generic) needs packages Varda does not ship
    hiddenimports=collect_submodules('rasterio')
    + collect_submodules('hypyrameter', filter=lambda name: 'iovf' not in name),
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
    [],
    exclude_binaries=True,
    name='Varda',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['resources/logo.ico', 'resources/logo.icns'],  # PyInstaller picks .ico on Windows, .icns on macOS
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Varda',
)
