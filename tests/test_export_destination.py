"""Offscreen Qt with mocked chooser/confirmation; never touches user files."""
import os
import time
from pathlib import Path

import pymupdf
import pytest
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from ui.export_dialog import ExportDialog
from utils.pdf_export import ExportDestination, export_pdf


@pytest.fixture
def inputs(tmp_path):
    paths = [tmp_path / name for name in ("source.pdf", "translated.pdf")]
    for path in paths:
        with pymupdf.open() as doc:
            doc.new_page().insert_text((72, 72), path.stem)
            doc.save(path)
    return paths


def finish(app, dialog):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and not dialog.export_button.isEnabled():
        app.processEvents()
        time.sleep(.01)
    assert dialog.export_button.isEnabled()
    if dialog.worker is not None:
        assert dialog.worker.wait(1000)


@pytest.mark.parametrize("choice", ["", "report", "report.pdf", "report.PDF"])
@pytest.mark.parametrize("approve", [False, True])
def test_final_filename_confirmation(app, inputs, tmp_path, monkeypatch, choice, approve):
    selected = str(tmp_path / choice) if choice else ""
    final = Path(selected if selected.lower().endswith(".pdf") else selected + ".pdf")
    if choice:
        final.write_bytes(b"existing sentinel")
    questions = []
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (selected, "PDF"))

    def question(parent, title, message, buttons, default):
        questions.append(message)
        assert str(final) in message
        assert default == QMessageBox.StandardButton.No
        return QMessageBox.StandardButton.Yes if approve else QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", question)
    dialog = ExportDialog(*map(str, inputs))
    dialog._export()
    finish(app, dialog)
    if not choice:
        assert not questions and dialog.worker is None
    elif approve:
        assert len(questions) == 1
        assert final.read_bytes().startswith(b"%PDF")
        assert "已导出" in dialog.status.text()
    else:
        assert len(questions) == 1
        assert final.read_bytes() == b"existing sentinel"
        assert dialog.worker is None
    dialog.deleteLater()


def test_new_extensionless_export_and_repeated_decline(app, inputs, tmp_path, monkeypatch):
    selected = tmp_path / "new"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(selected), "PDF"))
    questions = []
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a: questions.append(a) or QMessageBox.StandardButton.No)
    dialog = ExportDialog(*map(str, inputs))
    dialog._export()
    finish(app, dialog)
    before = selected.with_suffix(".pdf").read_bytes()
    assert not questions
    dialog._export()
    assert len(questions) == 1
    assert selected.with_suffix(".pdf").read_bytes() == before
    assert dialog.export_button.isEnabled()
    dialog.deleteLater()


def test_change_during_confirmation_is_preserved(app, inputs, tmp_path, monkeypatch):
    final = tmp_path / "report.pdf"
    final.write_bytes(b"old")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(final), "PDF"))

    def question(*args):
        final.write_bytes(b"changed while question open")
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", question)
    dialog = ExportDialog(*map(str, inputs))
    dialog._export()
    finish(app, dialog)
    assert final.read_bytes() == b"changed while question open"
    assert "导出失败" in dialog.status.text()
    assert set(tmp_path.iterdir()) == {*inputs, final}
    dialog.deleteLater()


@pytest.mark.parametrize("source_index", [0, 1])
@pytest.mark.parametrize("alias", ["direct", "relative", "symlink", "hardlink"])
def test_input_aliases_rejected(inputs, tmp_path, monkeypatch, source_index, alias):
    source = inputs[source_index]
    before = source.read_bytes()
    destination = tmp_path / "alias.pdf"
    if alias == "direct":
        destination = source
    elif alias == "relative":
        monkeypatch.chdir(tmp_path)
        destination = Path(source.name)
    else:
        try:
            if alias == "symlink":
                destination.symlink_to(source)
            else:
                os.link(source, destination)
        except OSError:
            pytest.skip("link creation unavailable")
    with pytest.raises(ValueError):
        ExportDestination.capture(*inputs, destination)
    with pytest.raises(ValueError):
        export_pdf(*inputs, destination)
    assert source.read_bytes() == before


@pytest.mark.parametrize("layout", ["translation", "side_by_side"])
@pytest.mark.parametrize("existing", [False, True])
def test_target_changed_during_generation_is_preserved(inputs, tmp_path, monkeypatch, layout, existing):
    destination = tmp_path / "report.pdf"
    if existing:
        destination.write_bytes(b"approved target")
    guard = ExportDestination.capture(*inputs, destination)
    import utils.pdf_export as module
    publish = ExportDestination.publish

    def changed(self, temporary, original, translated):
        destination.write_bytes(b"concurrent sentinel")
        return publish(self, temporary, original, translated)

    monkeypatch.setattr(ExportDestination, "publish", changed)
    with pytest.raises(FileExistsError):
        module.export_pdf(*inputs, destination, layout, destination_guard=guard)
    assert destination.read_bytes() == b"concurrent sentinel"
    assert set(tmp_path.iterdir()) == {*inputs, destination}


def test_target_appearing_after_last_check_is_not_clobbered(inputs, tmp_path, monkeypatch):
    destination = tmp_path / "new.pdf"
    guard = ExportDestination.capture(*inputs, destination)
    link = os.link

    def competing_link(src, dst):
        Path(dst).write_bytes(b"late sentinel")
        return link(src, dst)

    monkeypatch.setattr(os, "link", competing_link)
    with pytest.raises(FileExistsError):
        export_pdf(*inputs, destination, destination_guard=guard)
    assert destination.read_bytes() == b"late sentinel"
    assert set(tmp_path.iterdir()) == {*inputs, destination}


def test_unsupported_atomic_link_fails_without_replace(inputs, tmp_path, monkeypatch):
    destination = tmp_path / "new.pdf"
    guard = ExportDestination.capture(*inputs, destination)

    def unsupported(*args):
        raise OSError("hardlinks unsupported")

    monkeypatch.setattr(os, "link", unsupported)
    with pytest.raises(OSError, match="unsupported"):
        export_pdf(*inputs, destination, destination_guard=guard)
    assert not destination.exists()
    assert set(tmp_path.iterdir()) == set(inputs)


@pytest.mark.parametrize("kind", ["directory", "dangling_link"])
def test_nonregular_destination_rejected(inputs, tmp_path, kind):
    destination = tmp_path / "target.pdf"
    if kind == "directory":
        destination.mkdir()
    else:
        try:
            destination.symlink_to(tmp_path / "absent.pdf")
        except OSError:
            pytest.skip("symlink unavailable")
    with pytest.raises(ValueError):
        ExportDestination.capture(*inputs, destination)


def test_guard_cannot_authorize_different_path(inputs, tmp_path):
    guard = ExportDestination.capture(*inputs, tmp_path / "approved.pdf")
    with pytest.raises(ValueError, match="确认"):
        export_pdf(*inputs, tmp_path / "other.pdf", destination_guard=guard)
    assert set(tmp_path.iterdir()) == set(inputs)


def test_suffix_normalized_source_is_blocked_before_question(app, inputs, monkeypatch):
    original, translated = inputs
    before = original.read_bytes()
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        lambda *a, **k: (str(original.with_suffix("")), "PDF"))
    questions = []
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a: questions.append(a) or QMessageBox.StandardButton.Yes)
    dialog = ExportDialog(str(original), str(translated))
    dialog._export()
    assert not questions and dialog.worker is None
    assert "导出失败" in dialog.status.text()
    assert original.read_bytes() == before
    assert dialog.export_button.isEnabled()
    dialog.deleteLater()


def test_destination_becoming_input_alias_is_rejected(inputs, tmp_path):
    destination = tmp_path / "new.pdf"
    guard = ExportDestination.capture(*inputs, destination)
    try:
        os.link(inputs[0], destination)
    except OSError:
        pytest.skip("hardlink unavailable")
    before = inputs[0].read_bytes()
    with pytest.raises(ValueError):
        export_pdf(*inputs, destination, destination_guard=guard)
    assert inputs[0].read_bytes() == destination.read_bytes() == before
    assert set(tmp_path.iterdir()) == {*inputs, destination}
