# -*- mode: python ; coding: utf-8 -*-
# 把 Python 引擎冻结成单文件：dist/whsport-engine（Windows 为 .exe）。
#
# 注意：sport_client 顶层会 import geetest_solver（cv2 + playwright），因此产物较大。
# 若只想给 GUI 用、且不需要图形验证码，可把 geetest 改成惰性导入以显著瘦身。

block_cipher = None

a = Analysis(
    ['engine_entry.py'],
    pathex=['../src'],
    binaries=[],
    datas=[],
    hiddenimports=['whsport', 'whsport.rpc'],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='whsport-engine',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=True,
)
