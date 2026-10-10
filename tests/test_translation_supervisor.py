"""Exercise a genuinely stalled child process, not a mocked timeout callback."""
from pathlib import Path
import subprocess
import sys


def stalled_worker(job, events, cancellation):
    import pymupdf, shutil, time
    from utils.incremental_translation import checkpoint_paths
    partial, _ = checkpoint_paths(job['input_file'])
    shutil.copyfile(job['input_file'], partial)
    previews=Path(job['preview_dir']);previews.mkdir(parents=True)
    snapshot=previews/'snapshot.pdf';shutil.copyfile(partial,snapshot)
    events.put({'type':'document','total':2,'document_pages':2,'completed':0})
    events.put({'type':'checkpoint','path':str(partial),'preview_path':str(snapshot),'completed':1,'total':2,'document_pages':2,'completed_pages':[0]})
    events.put({'type':'request_started','active':1,'finished':1,'failed':0})
    time.sleep(20)


def exercise(directory):
    import os, pymupdf, time
    from unittest.mock import patch
    import core.translation as core
    pdf=directory/'source.pdf'
    with pymupdf.open() as doc:
        doc.new_page();doc.new_page();doc.save(pdf)
    os.environ['FREEPDF_DATA_DIR']=str(directory/'data')
    thread=core.TranslationThread(str(pdf))
    thread.logger.set_timeout(api_timeout=.35)
    failures=[];partial=[]
    thread.translation_failed.connect(failures.append)
    thread.translation_partial.connect(partial.append)
    start=time.monotonic()
    with patch.object(core,'translation_process',stalled_worker):thread.run()
    assert time.monotonic()-start<6
    assert failures and '已保存 1 页译文' in failures[0],failures
    assert partial and Path(partial[0]['path']).exists()
    assert thread._process is None
    assert thread.logger.get_state()['status']=='partial'
    with pymupdf.open(partial[0]['path']) as doc:assert doc.page_count==2


def test_stalled_process_is_stopped_and_saved_output_survives(tmp_path):
    result=subprocess.run([sys.executable,str(Path(__file__).resolve()),str(tmp_path)],capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stdout+result.stderr


if __name__=='__main__':
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
    exercise(Path(sys.argv[1]))
