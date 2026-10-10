"""Fail a release build on missing native dependencies, resources or wrong DLLs."""

from pathlib import Path
import os
import sys
import pefile


def main():
    root = Path(sys.argv[1]).resolve() / "_internal"
    native = sys.argv[2] == "native"
    qt = root / "PyQt6/Qt6"
    required = ["ui/logo/logo.png", "PyQt6/Qt6/bin/Qt6Pdf.dll", "PyQt6/Qt6/bin/Qt6PdfWidgets.dll"]
    if native:
        assert not list(root.rglob("*WebEngine*")), "Native package contains WebEngine"
    else:
        required += ["pdfjs/web/viewer.html", "pdfjs/build/pdf.worker.mjs",
                     "PyQt6/Qt6/bin/QtWebEngineProcess.exe", "PyQt6/Qt6/bin/Qt6WebEngineCore.dll",
                     "PyQt6/Qt6/bin/Qt6WebEngineWidgets.dll", "PyQt6/Qt6/resources/qtwebengine_resources.pak",
                     "PyQt6/Qt6/resources/icudtl.dat", "PyQt6/Qt6/resources/v8_context_snapshot.bin",
                     "PyQt6/Qt6/translations/qtwebengine_locales/en-US.pak"]
    for relative in required:
        assert (root / relative).is_file(), f"Missing packaged resource: {relative}"
    system = Path(os.environ['SystemRoot']) / 'System32'
    shipped = {p.name.lower(): p for p in [*root.glob('*.dll'), *(qt/'bin').glob('*.dll')]}
    for module in (qt/'bin').glob('*'):
        if module.suffix.lower() not in ('.dll', '.exe'):
            continue
        pe = pefile.PE(str(module), fast_load=True)
        assert pe.FILE_HEADER.Machine == 0x8664, f"Expected x64: {module.name}"
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT']])
        for item in getattr(pe, 'DIRECTORY_ENTRY_IMPORT', []):
            name = item.dll.decode('ascii').lower()
            if name.startswith(('api-ms-win-', 'ext-ms-win-')):
                continue
            assert name in shipped or (system/name).exists(), f"Missing {name}, required by {module.name}"
        pe.close()
    if not native:
        for name in ('msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll', 'msvcp140_1.dll', 'msvcp140_2.dll'):
            assert (qt/'bin'/name).is_file(), f"WebEngine helper lacks app-local VC runtime: {name}"
    print(f'Packaged {sys.argv[2]} native dependencies, architecture, resources and icons verified')


if __name__ == '__main__':
    main()
