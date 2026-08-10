"""
PyInstaller build specification for AI Stock Metadata Agent.

Usage:
    pyinstaller stock-metadata-agent.spec
"""

# -*- mode: python ; coding: utf-8 -*-

import os
import sys

block_cipher = None

# Determine platform
is_mac = sys.platform == 'darwin'
is_win = sys.platform == 'win32'

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config', 'config'),
        ('core', 'core'),
        ('ai', 'ai'),
        ('ui', 'ui'),
        ('db', 'db'),
        ('export', 'export'),
        ('resources', 'resources'),
    ],
    hiddenimports=[
        'config',
        'config.constants',
        'config.settings',
        'core',
        'core.scanner',
        'core.location',
        'core.location.parser',
        'core.location.gps',
        'core.metadata',
        'core.metadata.writer',
        'core.metadata.sidecar',
        'core.video',
        'core.video.extractor',
        'core.video.movement',
        'core.quality',
        'core.quality.scorer',
        'core.duplicate',
        'core.orchestrator',
        'core.report',
        'ai',
        'ai.client',
        'ai.vision',
        'ai.generator',
        'db',
        'db.memory',
        'export',
        'export.csv',
        'ui',
        'ui.window',
        'ui.panels',
        'ui.panels.batch',
        'ui.panels.preview',
        'ui.panels.report',
        'ui.panels.settings',
        'PIL',
        'PIL.Image',
        'imagehash',
        'cv2',
        'numpy',
        'exifread',
        'ffmpeg',
        'ffmpeg.runtime',
        'tenacity',
        'structlog',
        'requests',
        'urllib3',
        'urllib3.util',
        'urllib3.util.ssl_',
        'certifi',
        'charset_normalizer',
        'idna',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'unittest',
        'pytest',
        'setuptools',
        'wheel',
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if is_mac:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='stock-metadata-agent',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        icon='resources/icon.png',
    )
    app = BUNDLE(
        exe,
        name='AI Stock Metadata Agent.app',
        icon='resources/icon.png',
        bundle_identifier='com.stockmetadata.agent',
        info_plist={
            'CFBundleShortVersionString': '0.1.5',
            'CFBundleVersion': '0.1.5',
        },
        entitlements_file=None,
    )
    apps = [app]
elif is_win:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='stock-metadata-agent',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        icon=None,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        name='stock-metadata-agent',
    )
    apps = [coll]
else:
    # Linux
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='stock-metadata-agent',
        debug=False,
        console=False,
    )
    apps = []
