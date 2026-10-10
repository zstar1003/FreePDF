"""Exercise the released upstream engine and real ONNX model; replace only HTTP translation."""
from pathlib import Path
import importlib.metadata

import pymupdf


def test_latest_upstream_engine_produces_local_translation_and_wide_export(tmp_path,monkeypatch):
    from pdf2zh.high_level import translate
    from pdf2zh.doclayout import OnnxModel
    from pdf2zh.config import ConfigManager
    from pdf2zh.translator import GoogleTranslator
    from utils.pdf_export import export_pdf
    root=Path(__file__).resolve().parent.parent
    font=str(root/'fonts/SourceHanSerifCN-Regular.ttf')
    monkeypatch.setattr(ConfigManager,'get',lambda key,default=None:font if key=='NOTO_FONT_PATH' else default)
    translated_text='这是新版翻译引擎的验证结果。'
    calls=[]
    def offline_translate(self,text):
        calls.append(text)
        return translated_text
    monkeypatch.setattr(GoogleTranslator,'do_translate',offline_translate)
    path=tmp_path/'engine.pdf'
    with pymupdf.open() as doc:
        page=doc.new_page()
        page.insert_textbox(pymupdf.Rect(72,100,480,300),'This scientific paper presents a new research method. The translation keeps the original document layout and mathematics.',fontsize=16)
        doc.save(path)
    from utils.translation_engine import translate_preserving_source
    before=path.read_bytes()
    result=translate_preserving_source(translate,str(path),dict(output=str(tmp_path),lang_in='en',lang_out='zh',service='google',thread=1,
                     model=OnnxModel(str(root/'models/doclayout_yolo_docstructbench_imgsz1024.onnx')),
                     vfont=font,ignore_cache=True))
    assert path.read_bytes()==before
    assert importlib.metadata.version('pdf2zh')=='1.9.11'
    assert calls
    mono,dual=result[0]
    assert Path(mono).is_file() and Path(dual).is_file()
    with pymupdf.open(mono) as doc:
        assert doc.page_count==1
        assert '验证结果' in doc[0].get_text()
    destination=tmp_path/'wide.pdf'
    export_pdf(path,mono,destination)
    with pymupdf.open(destination) as doc:
        assert doc.page_count==1
        assert doc[0].rect.width>doc[0].rect.height
        assert 'scientific' in doc[0].get_text() and '验证结果' in doc[0].get_text()
