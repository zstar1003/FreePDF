"""Resolve complete viewer distributions in development and PyInstaller bundles."""

from pathlib import Path
import sys


def viewer_candidates():
    project = Path(__file__).resolve().parent.parent
    if not getattr(sys, "frozen", False):
        return [project / "pdfjs/web/viewer.html"]
    roots = []
    if hasattr(sys, "_MEIPASS"):
        roots.append(Path(sys._MEIPASS))
    roots.extend([Path(sys.executable).parent / "_internal", Path(sys.executable).parent])
    # Last two candidates per root support releases built with the old flattened datas entry.
    return list(dict.fromkeys(path for root in roots for path in (
        root / "pdfjs/web/viewer.html", root / "web/viewer.html",
    )))


def resolve_viewer():
    candidates = viewer_candidates()
    required = ("web/viewer.html", "web/viewer.mjs", "web/viewer.css", "build/pdf.mjs", "build/pdf.worker.mjs")
    checks = []
    for path in candidates:
        root = path.parent.parent
        missing = [item for item in required if not (root / item).is_file()]
        checks.append({"viewer": str(path), "missing": missing})
        if not missing:
            return path, checks
    raise FileNotFoundError("PDF.js resources missing: " + str(checks))
