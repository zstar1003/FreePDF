from pathlib import Path
import json
import threading

import pymupdf
import pytest
from utils.incremental_translation import checkpoint_paths, run_translation_job


def make_source(path):
    with pymupdf.open() as doc:
        for number in range(3):
            page = doc.new_page()
            page.insert_text((72, 100), f'Original page {number + 1}')
        doc.set_toc([[1, 'First', 1], [1, 'Last', 3]])
        doc.save(path)


def job_for(path, tmp_path):
    return dict(input_file=str(path), preview_dir=str(tmp_path/'previews'), lang_in='en', lang_out='zh',
                service='google', envs={}, threads=1, pages='', font='test-font', save_dual_file=False)


def fake_engine(calls, fail_after=None):
    def translate(files, output, **kwargs):
        with pymupdf.open(files[0]) as original:
            text = original[0].get_text().strip()
        calls.append(text)
        if fail_after is not None and len(calls) > fail_after:
            raise TimeoutError('service did not answer')
        mono = Path(output)/'page-mono.pdf'
        with pymupdf.open() as doc:
            page=doc.new_page()
            page.insert_text((72,100), text.replace('Original', 'Translated'))
            doc.save(mono)
        return [(str(mono), None)]
    return translate


def test_failure_keeps_completed_page_full_document_and_resume(tmp_path):
    path=tmp_path/'input.pdf';make_source(path)
    before=path.read_bytes();path.chmod(0o444)
    events=[];calls=[];job=job_for(path,tmp_path)
    run_translation_job(job, events.append, threading.Event(), fake_engine(calls,1))
    partial,manifest=checkpoint_paths(path)
    assert events[-1]['type']=='failed'
    assert events[-1]['completed']==1
    assert not path.with_name('input-mono.pdf').exists()
    with pymupdf.open(partial) as doc:
        assert doc.page_count==3
        assert 'Translated page 1' in doc[0].get_text()
        assert 'Original page 2' in doc[1].get_text()
        assert doc.get_toc()==[[1,'First',1],[1,'Last',3]]
    snapshot=Path(next(e for e in events if e['type']=='checkpoint')['preview_path'])
    saved_snapshot=snapshot.read_bytes()
    events=[];resume_calls=[];job["preview_dir"]=str(tmp_path/"resumed-previews")
    run_translation_job(job, events.append, threading.Event(), fake_engine(resume_calls))
    assert resume_calls==['Original page 2','Original page 3']
    assert events[-1]['type']=='completed'
    assert not partial.exists() and not manifest.exists()
    assert snapshot.read_bytes()==saved_snapshot
    assert path.read_bytes()==before
    path.chmod(0o666)
    with pymupdf.open(events[-1]['path']) as doc:
        assert all('Translated' in page.get_text() for page in doc)


def test_changed_settings_restart_checkpoint(tmp_path):
    path=tmp_path/'input.pdf';make_source(path)
    job=job_for(path,tmp_path)
    run_translation_job(job, lambda event:None, threading.Event(), fake_engine([],1))
    job['lang_out']='ja';calls=[];events=[]
    run_translation_job(job, events.append, threading.Event(), fake_engine(calls))
    assert len(calls)==3
    assert events[-1]['type']=='completed'


def test_page_selection_progress_uses_selected_pages_and_keeps_others(tmp_path):
    path=tmp_path/'input.pdf';make_source(path)
    job=job_for(path,tmp_path);job['pages']='2-3';events=[]
    run_translation_job(job, events.append, threading.Event(), fake_engine([]))
    commits=[e for e in events if e['type']=='checkpoint']
    assert [(e['completed'], e['total']) for e in commits]==[(1,2),(2,2)]
    with pymupdf.open(events[-1]['path']) as doc:
        assert 'Original' in doc[0].get_text()
        assert all('Translated' in doc[i].get_text() for i in (1,2))


def test_cancel_after_save_preserves_checkpoint(tmp_path):
    path=tmp_path/'input.pdf';make_source(path)
    cancellation=threading.Event();events=[]
    def receive(event):
        events.append(event)
        if event['type']=='checkpoint':cancellation.set()
    run_translation_job(job_for(path,tmp_path),receive,cancellation,fake_engine([]))
    assert events[-1]['type']=='stopped'
    partial,manifest=checkpoint_paths(path)
    assert partial.exists() and json.loads(manifest.read_text())['completed_pages']==[0]


def test_invalid_page_range_does_not_silently_translate_all(tmp_path):
    path=tmp_path/'input.pdf';make_source(path)
    job=job_for(path,tmp_path);job['pages']='1-9';events=[];calls=[]
    run_translation_job(job,events.append,threading.Event(),fake_engine(calls))
    assert events[-1]['type']=='failed' and '页码范围无效' in events[-1]['message']
    assert calls==[]


def test_changed_source_does_not_reuse_old_translated_page(tmp_path):
    path=tmp_path/'input.pdf';make_source(path)
    job=job_for(path,tmp_path)
    run_translation_job(job,lambda event:None,threading.Event(),fake_engine([],1))
    with pymupdf.open(path) as source:
        source[0].insert_text((72,160),'Changed source')
        new_path=tmp_path/'new.pdf';source.save(new_path)
    new_path.replace(path)
    calls=[];events=[]
    run_translation_job(job,events.append,threading.Event(),fake_engine(calls))
    assert len(calls)==3 and 'Changed source' in calls[0]
    assert events[-1]['type']=='completed'
