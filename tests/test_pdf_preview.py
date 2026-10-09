import ast
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from PyQt6.QtCore import QUrl

from ui.pdfjs_widget import build_viewer_url
from utils import pdfjs_paths

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("path", [
    "/tmp/中文 论文.pdf", "/tmp/paper&A=B#section+100%.pdf",
    "/tmp/literal%23and%25.pdf", "/tmp/query?test.pdf",
])
def test_file_url_round_trip_through_viewer_query(path):
    pdf = QUrl.fromLocalFile(path)
    viewer = build_viewer_url(ROOT / "pdfjs/web/viewer.html", pdf, "zh-cn")
    outer_url = viewer.toString(QUrl.ComponentFormattingOption.FullyEncoded)
    file_value = parse_qs(urlsplit(outer_url).query)["file"][0]
    assert file_value == pdf.toString(QUrl.ComponentFormattingOption.FullyEncoded)
    assert QUrl(file_value).toLocalFile() == path
    assert urlsplit(outer_url).fragment == "locale=zh-cn"


@pytest.mark.parametrize("url", [
    "file:///C:/Users/Test/Documents/%E4%B8%AD%E6%96%87%20A%26B%23C%25.pdf",
    "file://server/share/paper%26A%23B.pdf",
])
def test_windows_drive_and_unc_urls_keep_their_structure(url):
    encoded = build_viewer_url(ROOT / "pdfjs/web/viewer.html", QUrl(url)).toString(QUrl.ComponentFormattingOption.FullyEncoded)
    recovered = parse_qs(urlsplit(encoded).query)["file"][0]
    assert recovered == url
    assert QUrl(recovered).toString(QUrl.ComponentFormattingOption.FullyEncoded) == url


def test_viewer_resolution_is_independent_of_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    viewer, _ = pdfjs_paths.resolve_viewer()
    assert viewer == ROOT / "pdfjs/web/viewer.html"


@pytest.mark.parametrize("flattened", [False, True])
def test_complete_frozen_bundle_and_legacy_layout(tmp_path, monkeypatch, flattened):
    import sys
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    root = tmp_path if flattened else tmp_path / "pdfjs"
    for name in ("web/viewer.html", "web/viewer.mjs", "web/viewer.css", "build/pdf.mjs", "build/pdf.worker.mjs"):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    viewer, _ = pdfjs_paths.resolve_viewer()
    assert viewer == root / "web/viewer.html"


def test_missing_worker_is_reported_as_incomplete_distribution(tmp_path, monkeypatch):
    viewer = tmp_path / "pdfjs/web/viewer.html"
    viewer.parent.mkdir(parents=True)
    viewer.touch()
    monkeypatch.setattr(pdfjs_paths, "viewer_candidates", lambda: [viewer])
    with pytest.raises(FileNotFoundError, match="pdf.worker.mjs"):
        pdfjs_paths.resolve_viewer()


def test_windows_packaging_preserves_pdfjs_layout():
    from PyInstaller.building.utils import format_binaries_and_datas
    spec = ast.parse((ROOT / "build.spec").read_text())
    analysis = next(node for node in ast.walk(spec) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Analysis")
    data = ast.literal_eval(next(item.value for item in analysis.keywords if item.arg == "datas"))
    pdfjs_entries = [entry for entry in data if entry[0] == "pdfjs"]
    expanded = format_binaries_and_datas(pdfjs_entries, str(ROOT))
    destinations = {name.replace("\\", "/") for name, _ in expanded}
    assert "pdfjs/web/viewer.html" in destinations
    assert "pdfjs/build/pdf.worker.mjs" in destinations
