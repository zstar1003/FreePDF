# PDF preview diagnostics implementation plan

**Goal:** Repair known PDF preview failures and let users export local diagnostic logs from engine settings.

**Architecture:** A standard-library logging service starts before Qt and pdf2zh, persists bounded rotating logs, redacts credentials and exports logs plus environment metadata as a ZIP. PDF.js reports its own lifecycle separately from HTML navigation; each view tracks a load ID so failures can be traced independently of translation.

**Tech stack:** Python logging/zipfile, PyQt6 WebEngine, bundled PDF.js 5.3.0, pytest.

1. Verify Windows packaging layout with PyInstaller's data expansion helper; correct `pdfjs` destination and resolve viewer resources relative to the application rather than the working directory. Retain a fallback for the old flattened bundle.
2. Encode PDF file URLs as query values and remove PDF.js's extra decoding pass. Test Chinese, spaces, ampersands, hashes, percent signs, plus signs and Windows drive/UNC URLs.
3. Add rotating logs, startup metadata, exception and Qt message capture, credential redaction, and an export archive containing only logs and diagnostic metadata.
4. Record PDF import, file accessibility, resource checks, Qt navigation, PDF.js initialization/document/page events, JS errors, stalled preview state and renderer termination. Keep translation logs on disk even when the existing in-memory viewer is cleared.
5. Add a diagnostics dialog under engine settings: export logs and an opt-in software rendering mode applied after restart. Show actionable preview failure messages separately from translation progress.
6. Verify URL regressions, packaging paths, rotation/redaction/export, and real Qt WebEngine rendering of a PDF with a special-character filename. Exercise missing resources and invalid PDFs. Document Windows 11 reproduction and log interpretation; do not claim Windows verification from macOS.

## Evidence and acceptance

- Windows `build.spec` currently maps `pdfjs` to `.`; the reader searches `pdfjs/web/viewer.html`.
- Viewer navigation success is not PDF render success. Existing logging only prints JS warnings/errors and keeps translation logs in memory.
- The query is assembled manually; PDF.js also calls `decodeURIComponent` on an already decoded URLSearchParams value.
- Export must work without importing a PDF or starting a translation and must not include API configuration or PDF contents.
- GPU/driver problems remain a hypothesis until logs or Windows testing establish them.
