# Windows PDF preview and application icon implementation plan

**Goal:** Ship v6.0.0 that opens PDFs on Windows without starting the failing Qt WebEngine helper, restores installed application icons, and verifies actual packaged PDF rendering.

**Architecture:** Windows selects a native Qt PDF widget without importing WebEngine; macOS keeps PDF.js and switches to the same native reader on preview failure. A compatible widget interface preserves dual-pane scroll synchronization, zoom, document navigation and save. Application icons resolve from bundled resources independently of the working directory. Logging records renderer selection, document errors, rendered pages and bundled native libraries.

**Tech stack:** PyQt6 QtPdf/QtPdfWidgets, existing Qt WebEngine/PDF.js on macOS, Python diagnostics, PyInstaller/NSIS, pytest, local Developer ID signing.

1. Add `utils/preview_backend.py`, `utils/resources.py`, `ui/native_pdf_widget.py` and `ui/pdf_preview_widget.py`. Test real native page pixels, special filenames, invalid files, repeated imports, scroll/zoom and automatic WebEngine recovery.
2. Update `main.py` and `ui/main_window.py` to select the backend before importing WebEngine and to resolve/set both application and window icons from absolute bundle paths. Verify icons with an unrelated working directory.
3. Add Qt PDF native libraries to both specs; exclude WebEngine from the Windows package. Expand diagnostics with renderer selection and native DLL inventory. Native Windows settings explain automatic compatibility behavior.
4. Replace profile-only packaged smoke checks with a generated real PDF in both panes, exact render success markers, isolated working directory and Windows PATH. Assert the installed Windows package contains native PDF libraries/icon and no WebEngine dependency.
5. Run regression suites and packaged smoke checks, including a forced native macOS run and Windows CI. Build local Mac ARM64 app/DMG with the user's Developer ID signature, without notarization as already requested.
6. Publish v6.0.0 from the verified source, upload Windows installer, signed Mac DMG and SHA256SUMS; describe Windows native preview and the PDF.js annotation difference clearly in release notes.

Acceptance: No QtWebEngineProcess is required on Windows. The package must render a real PDF from a path containing Chinese, spaces and reserved URL characters with a clean PATH and independent working directory. Exported logs must identify the actual backend and the first rendered page. No user troubleshooting is required to select the Windows renderer.
