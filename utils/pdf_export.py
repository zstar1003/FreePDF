"""Atomic vector PDF exports: one original/translated page pair per wide page."""

import os
import shutil
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pymupdf


def validate_destination(original, translated, destination):
    """Reject source paths and aliases before any overwrite confirmation."""
    destination = Path(destination)
    for source in map(Path, (original, translated)):
        if destination.resolve() == source.resolve():
            raise ValueError("请选择新的文件名，原文和本地译文将保持完整。")
        try:
            if destination.samefile(source):
                raise ValueError("请选择新的文件名，原文和本地译文将保持完整。")
        except FileNotFoundError:
            pass


def _destination_signature(path):
    try:
        info = Path(path).lstat()
    except FileNotFoundError:
        return None
    # Do not replace links, directories, or devices through the export UI.
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("导出目标必须是普通文件，不能是链接或目录。")
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


@dataclass(frozen=True)
class ExportDestination:
    path: Path
    signature: object

    @classmethod
    def capture(cls, original, translated, destination):
        # Pin the absolute parent so later working-directory changes do not
        # redirect a relative selection. Do not resolve the final symlink.
        destination = Path(destination)
        destination = destination.parent.resolve() / destination.name
        validate_destination(original, translated, destination)
        return cls(destination, _destination_signature(destination))

    def publish(self, temporary, original, translated):
        validate_destination(original, translated, self.path)
        if _destination_signature(self.path) != self.signature:
            raise FileExistsError("导出目标已变化，请重新选择文件并确认。")
        if self.signature is None:
            # Atomic no-clobber publication: if another process creates the
            # destination after the check, linking fails rather than replacing.
            # Unsupported filesystems fail safely; never fall back to replace.
            os.link(temporary, self.path)
            temporary.unlink()
        else:
            # Recheck the confirmed file immediately before replacement.
            # Portable filesystems have no compare-and-replace primitive:
            # this detects changes during generation, not hostile last-instant
            # changes to the file or its parent directory.
            os.replace(temporary, self.path)


def export_pdf(original, translated, destination, layout="side_by_side", *, destination_guard=None):
    original, translated, destination = map(Path, (original, translated, destination))
    validate_destination(original, translated, destination)
    if destination_guard is not None and destination.absolute() != destination_guard.path:
        raise ValueError("导出目标与确认的路径不一致。")
    if layout not in ("side_by_side", "translation"):
        raise ValueError("不支持的导出格式")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".pdf", delete=False) as stream:
            temporary = Path(stream.name)
        if layout == "translation":
            with pymupdf.open(translated) as check:
                if not check.page_count or check.needs_pass:
                    raise ValueError("译文 PDF 无法读取")
            shutil.copyfile(translated, temporary)
        else:
            with pymupdf.open(original) as source, pymupdf.open(translated) as target, pymupdf.open() as output:
                if source.needs_pass or target.needs_pass:
                    raise ValueError("请先解锁受密码保护的 PDF")
                if not source.page_count or source.page_count != target.page_count:
                    raise ValueError("原文与译文页数不一致，无法逐页配对。请导出译文版本。")
                margin, gutter = 12, 16
                for index in range(source.page_count):
                    left, right = source[index].rect, target[index].rect
                    height = max(left.height, right.height)
                    page = output.new_page(width=left.width + right.width + 2 * margin + gutter,
                                           height=height + 2 * margin)
                    left_box = pymupdf.Rect(margin, margin, margin + left.width, margin + left.height)
                    right_box = pymupdf.Rect(margin + left.width + gutter, margin,
                                            margin + left.width + gutter + right.width, margin + right.height)
                    # Empty source pages have no PDF content streams to import.
                    if source[index].get_contents():
                        page.show_pdf_page(left_box, source, index)
                    if target[index].get_contents():
                        page.show_pdf_page(right_box, target, index)
                    x = margin + left.width + gutter / 2
                    page.draw_line(pymupdf.Point(x, margin), pymupdf.Point(x, margin + height),
                                   color=(.82, .87, .88), width=.5)
                output.set_metadata({"title": original.stem + " - Bilingual", "creator": "FreePDF 6.0",
                                     "subject": "Original on the left; translation on the right"})
                output.save(temporary, garbage=4, deflate=True)
        if destination_guard is None:
            # Automatic bilingual exports retain their existing replacement policy.
            validate_destination(original, translated, destination)
            os.replace(temporary, destination)
        else:
            destination_guard.publish(temporary, original, translated)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return destination
