"""Require two real rendered PDF panes and installed icons in an isolated launcher."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import pymupdf


def main():
    executable=Path(sys.argv[1]).resolve()
    backend = sys.argv[2] if len(sys.argv)>2 else "pdfjs"
    translation = "--translation" in sys.argv
    with tempfile.TemporaryDirectory(prefix='freepdf-packaged-') as temporary:
        root=Path(temporary)
        pdf=root/'中文 & # + % sample.pdf'
        with pymupdf.open() as doc:
            for index in range(2 if translation else 1):
                page=doc.new_page()
                page.insert_textbox(pymupdf.Rect(72,90,480,230),f'FreePDF packaged rendering verification page {index + 1}. This scientific paper presents a new research method.',fontsize=18)
                page.draw_rect(pymupdf.Rect(72,250,250,350),fill=(0,0,0))
            doc.save(pdf)
        environment=dict(os.environ)
        environment.pop('FREEPDF_PREVIEW_BACKEND',None)
        for key in list(environment):
            if key.startswith(('QT_', 'QTWEBENGINE_', 'QML', 'PYTHONPATH')):
                environment.pop(key,None)
        # WebEngine needs a real macOS graphics context; Windows' native PDF
        # reader can be verified without a desktop graphics session.
        platform = 'cocoa' if sys.platform == 'darwin' else 'offscreen' if backend == 'native' else 'windows'
        environment.update(FREEPDF_DATA_DIR=str(root/'data'),QT_QPA_PLATFORM=platform)
        if sys.platform=='win32':
            windows=Path(environment.get('SystemRoot',r'C:\Windows'))
            environment['PATH']=os.pathsep.join(str(windows/p) for p in ('System32','',r'System32\Wbem'))
        log=root/'data/logs/freepdf.log'
        with (root/'console.log').open('w',encoding='utf-8') as console:
            arguments=[str(executable),'--preview-smoke',str(pdf)] + (['--translation-smoke'] if translation else [])
            process=subprocess.Popen(arguments,cwd=root,env=environment,
                                     stdout=console,stderr=subprocess.STDOUT)
            try:
                code=process.wait(timeout=150 if translation else 65)
                content=log.read_text('utf-8',errors='replace') if log.exists() else ''
                if code!=0 or 'packaged_preview_verified' not in content:
                    raise RuntimeError(f'Packaged preview failed: exit={code}\n{content[-16000:]}')
                if 'pdf2zh模块预加载成功' not in content or '初始化tiktoken失败' in content:
                    raise RuntimeError('Packaged translation preload did not pass\n'+content[-12000:])
                if backend == 'native' and "'backend': 'qt_pdf'" not in content:
                    raise RuntimeError('Native package did not use the native reader\n'+content[-12000:])
                if backend == 'pdfjs' and ('renderer_terminated' in content or 'event=native_recovery' in content or 'event=first_page_rendered' not in content):
                    raise RuntimeError('PDF.js package did not render with PDF.js\n'+content[-12000:])
                if translation and 'packaged_translation_verified completed=2 total=2' not in content:
                    raise RuntimeError('Packaged translation subprocess did not complete both pages\n'+content[-12000:])
                print('Packaged PDF rendered in both panes; installed window/application icons and translation preload verified')
            except Exception:
                console.flush()
                print((root/'console.log').read_text('utf-8',errors='replace')[-12000:])
                raise
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:process.wait(timeout=5)
                    except subprocess.TimeoutExpired:process.kill();process.wait()


if __name__=='__main__':
    main()
