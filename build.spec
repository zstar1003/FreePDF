# -*- mode: python ; coding: utf-8 -*-

import os
import glob
import shutil
import ast
from PyInstaller.utils.hooks import copy_metadata
from PyInstaller.building.utils import format_binaries_and_datas

# 获取当前目录
current_dir = os.path.dirname(os.path.abspath(SPEC))

configuration = ast.parse(open(os.path.join(current_dir, 'utils', 'build_config.py'), encoding='utf-8').read())
native_preview = next(ast.literal_eval(node.value) for node in configuration.body if isinstance(node, ast.Assign)) == 'native'
webengine_imports = ['PyQt6.QtWebEngineCore', 'PyQt6.QtWebEngineWidgets', 'PyQt6.QtWebChannel']

# 查找onnxruntime DLL文件
def find_onnx_binaries():
    binaries = []
    try:
        import onnxruntime
        onnx_path = os.path.dirname(onnxruntime.__file__)
        print(f"onnxruntime路径: {onnx_path}")
        
        # 添加onnxruntime的DLL文件 - 直接放到主目录
        onnx_dlls = glob.glob(os.path.join(onnx_path, "capi", "*.dll"))
        for dll in onnx_dlls:
            binaries.append((dll, '.'))  # 放到主目录
            print(f"添加onnxruntime DLL到主目录: {dll}")
        
        # 添加可能的其他DLL
        other_dlls = glob.glob(os.path.join(onnx_path, "*.dll"))
        for dll in other_dlls:
            binaries.append((dll, '.'))  # 放到主目录
            print(f"添加onnxruntime其他DLL到主目录: {dll}")
            
        # 检查是否有providers目录
        providers_path = os.path.join(onnx_path, "capi", "providers")
        if os.path.exists(providers_path):
            provider_dlls = glob.glob(os.path.join(providers_path, "*.dll"))
            for dll in provider_dlls:
                binaries.append((dll, '.'))  # 放到主目录
                print(f"添加provider DLL到主目录: {dll}")
                
    except ImportError as e:
        print(f"无法导入onnxruntime: {e}")
    
    return binaries

# 查找Visual C++ Redistributable DLL
def find_vc_redist_dlls():
    binaries = []
    vc_dlls = [
        "msvcp140.dll",
        "vcruntime140.dll", 
        "vcruntime140_1.dll",
        "msvcp140_1.dll",
        "msvcp140_2.dll",
        "concrt140.dll",
        "vcomp140.dll"
    ]
    
    search_dirs = [
        "C:\\Windows\\System32",
    ]
    
    for dll_name in vc_dlls:
        for search_dir in search_dirs:
            dll_path = os.path.join(search_dir, dll_name)
            if os.path.exists(dll_path):
                binaries.append((dll_path, '.'))  # 也放到主目录
                print(f"添加VC++ DLL到主目录: {dll_path}")
                break
    
    return binaries

# 查找可能的其他依赖DLL
def find_additional_dlls():
    binaries = []
    additional_dlls = [
        "libiomp5md.dll",  # Intel OpenMP
        "tbb.dll",         # Intel TBB
        "tbbmalloc.dll",   # Intel TBB malloc
        "mkl_*.dll",       # Intel MKL
    ]
    
    search_dirs = [
        "C:\\Windows\\System32",
        "C:\\Program Files\\Intel",
        "C:\\Program Files (x86)\\Intel",
    ]
    
    for dll_pattern in additional_dlls:
        for search_dir in search_dirs:
            dll_files = glob.glob(os.path.join(search_dir, dll_pattern))
            for dll_file in dll_files:
                if os.path.exists(dll_file):
                    binaries.append((dll_file, '.'))
                    print(f"添加额外DLL到主目录: {dll_file}")
    
    return binaries

block_cipher = None

# 收集所有二进制文件
onnx_binaries = find_onnx_binaries()
vc_binaries = find_vc_redist_dlls()
additional_binaries = find_additional_dlls()
all_binaries = onnx_binaries + vc_binaries + additional_binaries

print(f"找到 {len(onnx_binaries)} 个onnxruntime DLL文件")
print(f"找到 {len(vc_binaries)} 个VC++ Redistributable DLL文件")
print(f"找到 {len(additional_binaries)} 个额外DLL文件")

a = Analysis(
    ['main.py'],
    pathex=[current_dir],
    binaries=all_binaries,
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
        'PyQt6.QtPdf',
        'PyQt6.QtPdfWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        
        # onnxruntime相关 - 添加更多隐式导入
        'onnxruntime',
        'onnxruntime.capi',
        'onnxruntime.capi.onnxruntime_pybind11_state',
        'onnxruntime.capi._pybind_state',
        'onnxruntime.backend',
        'onnxruntime.backend.backend',
        'onnxruntime.backend.backend_rep',
        'onnxruntime.capi.onnxruntime_validation',
        
        # 其他依赖
        'pymupdf ',
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
    ] + ([] if native_preview else webengine_imports),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[os.path.join(current_dir, 'diagnostics_hook.py'), os.path.join(current_dir, 'onnxruntime_hook.py')],
    excludes=webengine_imports + ['PyQt6.QtWebEngineQuick'] if native_preview else [],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)


# The Chromium helper does not inherit Python's AddDllDirectory handles.
# Ship the same app-local runtime next to the helper, including newer MSVC parts.
if not native_preview:
    for source, _ in vc_binaries:
        a.binaries.append(('PyQt6/Qt6/bin/' + os.path.basename(source), source, 'BINARY'))

# Retain installed component versions in exported support diagnostics.
for package in ('PyQt6', 'PyQt6-Qt6', 'PyMuPDF', 'pdf2zh', 'pyinstaller') + (() if native_preview else ('PyQt6-WebEngine', 'PyQt6-WebEngine-Qt6')):
    a.datas += [(destination, source, 'DATA') for destination, source in format_binaries_and_datas(copy_metadata(package))]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FreePDF',
    debug=False,  # 关闭调试模式，正式发布版本
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 禁用控制台，正式发布版本
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='ui/logo/logo.ico' if os.path.exists(os.path.join(current_dir, 'ui/logo/logo.ico')) else None,
    # 添加运行时选项
    runtime_tmpdir=None,
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
