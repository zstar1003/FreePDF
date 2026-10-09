# -*- mode: python ; coding: utf-8 -*-

import os
import glob
import shutil
from PyInstaller.utils.hooks import copy_metadata
from PyInstaller.building.utils import format_binaries_and_datas
from PyInstaller.config import CONF
import sys

# 获取当前目录
current_dir = os.path.dirname(os.path.abspath(SPEC))

# 查找onnxruntime动态库文件
def find_onnx_binaries():
    binaries = []
    try:
        import onnxruntime
        onnx_path = os.path.dirname(onnxruntime.__file__)
        print(f"onnxruntime路径: {onnx_path}")

        # 添加onnxruntime的dylib文件
        onnx_libs = glob.glob(os.path.join(onnx_path, "capi", "*.dylib"))
        for lib in onnx_libs:
            binaries.append((lib, 'onnxruntime/capi'))
            print(f"添加onnxruntime dylib: {lib}")

        # 添加可能的其他库文件
        other_libs = glob.glob(os.path.join(onnx_path, "*.dylib"))
        for lib in other_libs:
            binaries.append((lib, 'onnxruntime'))
            print(f"添加onnxruntime其他dylib: {lib}")

    except ImportError as e:
        print(f"无法导入onnxruntime: {e}")

    return binaries

block_cipher = None

# 收集所有二进制文件
onnx_binaries = find_onnx_binaries()

print(f"找到 {len(onnx_binaries)} 个onnxruntime动态库文件")

a = Analysis(
    ['main.py'],
    pathex=[current_dir],
    binaries=onnx_binaries,
    datas=[
        # 配置文件
        ('pdf2zh_config.json', '.'),
        # ui文件
        ('ui', 'ui'),
        # 模型文件
        ('models/', 'models/'),
        # 字体文件
        ('fonts/', 'fonts/'),
        # 渲染器文件
        ('pdfjs', 'pdfjs'),
    ],
    hiddenimports=[
        # pdf2zh相关
        'pdf2zh',
        'pdf2zh.translate',
        'pdf2zh.config',
        'pdf2zh.doclayout',

        # PyQt6相关
        'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtWebEngineCore',
        'PyQt6.QtWebChannel',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',

        # onnxruntime相关
        'onnxruntime',
        'onnxruntime.capi',
        'onnxruntime.capi.onnxruntime_pybind11_state',
        'onnxruntime.capi._pybind_state',
        'onnxruntime.backend',
        'onnxruntime.backend.backend',
        'onnxruntime.backend.backend_rep',
        'onnxruntime.capi.onnxruntime_validation',

        # 其他依赖
        'pymupdf',
        'PyMuPDF',
        'PIL',
        'PIL.Image',
        'numpy',
        'cv2',
        'requests',
        'urllib3',
        'googletrans',
        'tiktoken_ext.openai_public',

        # 多进程支持
        'multiprocessing',
        'multiprocessing.pool',
        'multiprocessing.queues',
        'multiprocessing.context',
        'multiprocessing.spawn',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[
        os.path.join(current_dir, 'onnxruntime_hook.py'),
        os.path.join(current_dir, 'cv2_hook.py'),
    ],
    excludes=[
        'opencv-python-headless',  # 避免与opencv-python冲突
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# OpenCV resolves its Python loader through Resources symlinks, while PyInstaller
# places the native extension under Frameworks. Point the loader at _MEIPASS
# before BUNDLE seals and signs the app; no post-sign bundle edits are needed.
cv2_config = os.path.join(CONF['workpath'], 'cv2-config-3.py')
with open(cv2_config, 'w', encoding='utf-8') as config_file:
    config_file.write("sys.OpenCV_REPLACE_SYS_PATH_0 = True\nPYTHON_EXTENSIONS_PATHS = [os.path.join(sys._MEIPASS, 'cv2')] + PYTHON_EXTENSIONS_PATHS\n")
for index, (destination, source, kind) in enumerate(a.datas):
    if destination == 'cv2/config-3.py':
        a.datas[index] = (destination, cv2_config, kind)
        break
else:
    raise RuntimeError('OpenCV loader configuration was not collected')


# Retain installed component versions in exported support diagnostics.
for package in ('PyQt6', 'PyQt6-Qt6', 'PyQt6-WebEngine', 'PyQt6-WebEngine-Qt6', 'PyMuPDF', 'pdf2zh', 'pyinstaller'):
    a.datas += [(destination, source, 'DATA') for destination, source in format_binaries_and_datas(copy_metadata(package))]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FreePDF',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='arm64',  # 针对Apple Silicon
    codesign_identity=os.environ.get('SIGN_IDENTITY'),
    entitlements_file='entitlements.plist',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FreePDF',
)

app = BUNDLE(
    coll,
    name='FreePDF.app',
    icon='ui/logo/logo.icns',
    bundle_identifier='com.zstar.freepdf',
    version='5.1.3',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSAppleScriptEnabled': False,
        'CFBundleName': 'FreePDF',
        'CFBundleDisplayName': 'FreePDF',
        'CFBundleVersion': '5.1.3',
        'CFBundleShortVersionString': '5.1.3',
        'NSHighResolutionCapable': 'True',
        'LSMinimumSystemVersion': '10.15.0',
        'NSRequiresAquaSystemAppearance': False,
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'PDF Document',
                'CFBundleTypeRole': 'Viewer',
                'LSItemContentTypes': ['com.adobe.pdf'],
                'LSHandlerRank': 'Alternate',
            }
        ],
    },
)
