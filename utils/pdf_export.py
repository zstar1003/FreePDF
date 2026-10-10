"""Atomic vector PDF exports: one original/translated page pair per wide page."""

import os
from pathlib import Path
import shutil
import tempfile

import pymupdf


def export_pdf(original, translated, destination, layout="side_by_side"):
    original, translated, destination = map(Path, (original, translated, destination))
    if destination.resolve() in (original.resolve(), translated.resolve()):
        raise ValueError("请选择新的文件名，原文和本地译文将保持完整。")
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
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return destination
