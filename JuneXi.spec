# -*- mode: python ; coding: utf-8 -*-
# 六月息 · PyInstaller onedir 打包定义
# 构建: venv\Scripts\pyinstaller.exe JuneXi.spec --noconfirm --clean
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs

hiddenimports = ['pyodbc', 'clr', 'opencc', 'rapidocr', 'guji_punct', 'entity_tag']
hiddenimports += collect_submodules('webview')
hiddenimports += collect_submodules('rapidocr')

datas = [
    ('templates', 'templates'),
    ('static', 'static'),
    ('plugins', 'plugins'),
    ('docs', 'docs'),
    ('data/toolbooks', 'data/toolbooks'),
]
datas += collect_data_files('webview')
datas += collect_data_files('clr_loader')
datas += collect_data_files('opencc')
datas += collect_data_files('rapidocr')

binaries = []
binaries += collect_dynamic_libs('webview')
binaries += collect_dynamic_libs('clr_loader')

a = Analysis(
    ['desktop.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=['venv'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='JuneXi',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon='app.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='JuneXi',
)
