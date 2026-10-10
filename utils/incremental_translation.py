"""Page checkpoints owned by an isolated, cancellable translation process."""

from pathlib import Path
import hashlib
import json
import os
import shutil
import tempfile
import threading
import traceback
import uuid

from utils.diagnostics import get_logger, redact, register_secrets


def parse_pages(value, count):
    if not value or not str(value).strip():
        return list(range(count))
    pages = set()
    for part in str(value).split(","):
        ends = part.strip().split("-")
        start = int(ends[0])
        end = int(ends[1]) if len(ends) == 2 else start
        if len(ends) > 2 or start < 1 or end < start or end > count:
            raise ValueError(f"页码范围无效：{part}（文档共 {count} 页）")
        pages.update(range(start - 1, end))
    return sorted(pages)


def checkpoint_paths(source):
    source = Path(source)
    return source.with_name(source.stem + "-partial-mono.pdf"), source.with_name(source.stem + "-partial.freepdf.json")


def _atomic_json(path, data):
    handle = tempfile.NamedTemporaryFile(dir=path.parent, prefix=".freepdf-", suffix=".json", delete=False)
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_pdf(document, path):
    handle = tempfile.NamedTemporaryFile(dir=path.parent, prefix=".freepdf-", suffix=".pdf", delete=False)
    temporary = Path(handle.name)
    handle.close()
    try:
        document.save(temporary, garbage=3, deflate=True)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _fingerprint(source, job, selected):
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    # Credentials affect the request but never enter a manifest or event log.
    settings = {key: job.get(key) for key in ("lang_in", "lang_out", "service", "envs", "font")}
    settings["font"] = Path(job.get("font", "")).name
    settings["pages"] = selected
    settings["checkpoint_format"] = 1
    settings_digest = hashlib.sha256(json.dumps(settings, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {"source_sha256": digest.hexdigest(), "settings_sha256": settings_digest}


def run_translation_job(job, emit, cancellation, engine=None):
    """Translate one page at a time; completion events follow durable saves."""
    import pymupdf
    source = Path(job["input_file"]).resolve()
    partial, manifest_path = checkpoint_paths(source)
    completed = set()
    document = None
    restore_engine = None
    register_secrets(job.get("envs", {}).values())
    log = get_logger("translation.worker")
    try:
        emit({"type": "stage", "stage": "检查文档与断点"})
        with pymupdf.open(source) as original:
            if original.needs_pass:
                raise ValueError("请先解除 PDF 密码保护")
            count = original.page_count
            selected = parse_pages(job.get("pages", ""), count)
            if not selected:
                raise ValueError("没有可翻译的页面")
            fingerprint = _fingerprint(source, job, selected)
            table_of_contents = original.get_toc()
        if partial.exists() and manifest_path.exists():
            try:
                saved = json.loads(manifest_path.read_text("utf-8"))
                if all(saved.get(key) == value for key, value in fingerprint.items()):
                    candidate = pymupdf.open(partial)
                    saved_pages = set(saved.get("completed_pages", []))
                    if candidate.page_count == count and saved_pages <= set(selected):
                        document, completed = candidate, saved_pages
                    else:
                        candidate.close()
                else:
                    log.info("checkpoint ignored: source or translation settings changed")
            except Exception:
                log.exception("checkpoint unreadable; restarting from original")
        if document is None:
            document = pymupdf.open(source)

        snapshots = Path(job["preview_dir"])
        snapshots.mkdir(parents=True, exist_ok=True)

        def publish():
            snapshot = snapshots / f"preview-{len(completed):06d}-{uuid.uuid4().hex[:8]}.pdf"
            shutil.copyfile(partial, snapshot)
            emit({"type": "checkpoint", "path": str(partial), "preview_path": str(snapshot),
                  "completed_pages": sorted(completed), "completed": len(completed),
                  "total": len(selected), "document_pages": count})
            # Old snapshots are not overwritten while a Windows viewer holds them.
            for old in sorted(snapshots.glob("preview-*.pdf"), key=lambda p: p.stat().st_mtime)[:-3]:
                try:
                    old.unlink()
                except OSError:
                    pass

        emit({"type": "document", "total": len(selected), "document_pages": count,
              "completed": len(completed), "completed_pages": sorted(completed)})
        if completed:
            publish()
        emit({"type": "stage", "stage": "加载版面识别模型"})
        if engine is None:
            from pdf2zh.high_level import translate
            from pdf2zh.doclayout import OnnxModel
            from pdf2zh.config import ConfigManager
            from pdf2zh.translator import BaseTranslator, GoogleTranslator
            import pdf2zh.converter as converter
            from tenacity import retry, stop_after_attempt
            ConfigManager.set("NOTO_FONT_PATH", Path(job["font"]).as_posix())
            model = OnnxModel(job["model_path"])
            # The upstream paragraph worker retries forever. Bound that loop;
            # an unresponsive HTTP call is bounded by the supervising process.
            original_retry = converter.retry
            converter.retry = lambda **kwargs: retry(stop=stop_after_attempt(3), reraise=True, **kwargs)
            original_translate = BaseTranslator.translate
            original_google = GoogleTranslator.do_translate
            restore_engine = lambda: (setattr(BaseTranslator, "translate", original_translate), setattr(converter, "retry", original_retry), setattr(GoogleTranslator, "do_translate", original_google))
            request_lock = threading.Lock()
            requests = {"active": 0, "finished": 0, "failed": 0}

            def measured_translate(translator, text, *args, **kwargs):
                if cancellation.is_set():
                    raise RuntimeError("翻译已停止")
                with request_lock:
                    requests["active"] += 1
                    emit({"type": "request_started", **requests})
                success = False
                try:
                    result = original_translate(translator, text, *args, **kwargs)
                    success = True
                    return result
                finally:
                    with request_lock:
                        requests["active"] -= 1
                        requests["finished" if success else "failed"] += 1
                        emit({"type": "request_finished" if success else "request_failed", **requests})

            BaseTranslator.translate = measured_translate
            if job.get("smoke_test"):
                # Used only by the explicit packaged translation verification CLI.
                GoogleTranslator.do_translate = lambda self, text: "这是打包后逐页翻译的验证结果。"
            engine = translate
        else:
            model = job.get("model")
        from utils.translation_engine import translate_preserving_source
        original_subset = pymupdf.Document.subset_fonts

        def safe_subset(doc, *args, **kwargs):
            try:
                return original_subset(doc, *args, **kwargs)
            except ValueError as error:
                log.warning("font subset skipped: %s", error)

        pymupdf.Document.subset_fonts = safe_subset
        try:
            with tempfile.TemporaryDirectory(prefix="freepdf-pages-") as working:
                working = Path(working)
                for page_index in selected:
                    if cancellation.is_set():
                        emit({"type": "stopped", "message": "翻译已停止，已完成页面已保留"})
                        return
                    if page_index in completed:
                        continue
                    emit({"type": "page_started", "page": page_index + 1, "stage": "识别页面布局"})
                    log.info("page=%s selected=%s completed=%s event=page_started", page_index + 1, len(selected), len(completed))
                    page_file = working / "page.pdf"
                    with pymupdf.open(source) as original, pymupdf.open() as single:
                        single.insert_pdf(original, from_page=page_index, to_page=page_index)
                        single.save(page_file)
                    parameters = dict(output=str(working), lang_in=job["lang_in"], lang_out=job["lang_out"],
                                      service="openai" if job["service"] == "自定义" else job["service"],
                                      thread=job["threads"], envs=job.get("envs", {}), model=model, ignore_cache=bool(job.get("smoke_test")))
                    result = translate_preserving_source(engine, page_file, parameters)
                    if not result:
                        raise ValueError(f"第 {page_index + 1} 页翻译未生成结果")
                    with pymupdf.open(result[0][0]) as translated:
                        if translated.page_count != 1:
                            raise ValueError("单页翻译输出页数异常")
                        document.delete_page(page_index)
                        document.insert_pdf(translated, start_at=page_index)
                    # Do not mark a page complete until its PDF and manifest are saved.
                    emit({"type": "stage", "stage": "保存已完成页面"})
                    document.set_toc(table_of_contents)
                    _atomic_pdf(document, partial)
                    completed.add(page_index)
                    _atomic_json(manifest_path, {**fingerprint, "completed_pages": sorted(completed),
                                                "total": len(selected), "document_pages": count, "job_id": snapshots.name})
                    log.info("page=%s completed=%s total=%s event=checkpoint_saved", page_index + 1, len(completed), len(selected))
                    publish()
                    for generated in working.glob("*.pdf"):
                        generated.unlink(missing_ok=True)
        finally:
            pymupdf.Document.subset_fonts = original_subset
        mono = source.with_name(source.stem + "-mono.pdf")
        emit({"type": "stage", "stage": "生成最终 PDF"})
        _atomic_pdf(document, mono)
        if job.get("save_dual_file"):
            from utils.pdf_export import export_pdf
            export_pdf(source, mono, source.with_name(source.stem + "-dual.pdf"))
        partial.unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)
        emit({"type": "completed", "path": str(mono), "completed": len(completed), "total": len(selected)})
    except Exception as error:
        log.error("translation worker failed: %s\n%s", redact(str(error)), redact(traceback.format_exc()))
        emit({"type": "failed", "message": redact(str(error)), "completed": len(completed),
              "partial_path": str(partial) if completed and partial.exists() else None})
    finally:
        if restore_engine is not None:
            restore_engine()
        if document is not None:
            document.close()


def translation_process(job, events, cancellation):
    # This function is the spawn target. No QApplication exists in this process.
    from utils.diagnostics import initialize_logging
    initialize_logging(capture_console=True)
    run_translation_job(job, events.put, cancellation)
