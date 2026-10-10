"""Verify the upstream engine in its own process, as it loads before Qt at startup."""
from pathlib import Path
import importlib.metadata
import subprocess
import sys


def _exercise_engine(directory):
    # Qt and ONNX carry native dependencies on Windows. Keep this exercise in
    # the same import order as the application, independent of GUI test order.
    from pdf2zh.high_level import translate
    from pdf2zh.doclayout import OnnxModel
    from pdf2zh.config import ConfigManager
    from pdf2zh.translator import GoogleTranslator
    import pymupdf
    from unittest.mock import patch
    from utils.pdf_export import export_pdf
    from utils.translation_engine import translate_preserving_source
    root=Path(__file__).resolve().parent.parent
    font=str(root/'fonts/SourceHanSerifCN-Regular.ttf')
    translated_text='这是新版翻译引擎的验证结果。'
    calls=[]
    def offline_translate(self,text):
        calls.append(text)
        return translated_text
    path=directory/'engine.pdf'
    with pymupdf.open() as doc:
        page=doc.new_page()
        page.insert_textbox(pymupdf.Rect(72,100,480,300),'This scientific paper presents a new research method. The translation keeps the original document layout and mathematics.',fontsize=16)
        doc.save(path)
    before=path.read_bytes()
    with patch.object(ConfigManager,'get',side_effect=lambda key,default=None:font if key=='NOTO_FONT_PATH' else default), patch.object(GoogleTranslator,'do_translate',offline_translate):
        result=translate_preserving_source(translate,str(path),dict(output=str(directory),lang_in='en',lang_out='zh',service='google',thread=1,
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
    destination=directory/'wide.pdf'
    export_pdf(path,mono,destination)
    with pymupdf.open(destination) as doc:
        assert doc.page_count==1
        assert doc[0].rect.width>doc[0].rect.height
        assert 'scientific' in doc[0].get_text() and '验证结果' in doc[0].get_text()


def test_latest_upstream_engine_produces_local_translation_and_wide_export(tmp_path):
    root=Path(__file__).resolve().parent.parent
    result=subprocess.run([sys.executable,str(Path(__file__).resolve()),str(tmp_path)],cwd=root,capture_output=True,text=True,timeout=90)
    assert result.returncode==0,result.stdout+'\n'+result.stderr


if __name__=='__main__':
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
    _exercise_engine(Path(sys.argv[1]))
