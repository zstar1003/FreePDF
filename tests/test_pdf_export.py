from pathlib import Path
import pymupdf
import pytest
from utils.pdf_export import export_pdf


def document(path, text, sizes=((300,400),(500,300))):
    with pymupdf.open() as doc:
        for i,(width,height) in enumerate(sizes):
            page=doc.new_page(width=width,height=height)
            page.insert_text((25,40),f'{text} {i+1}')
        doc.save(path)


def test_side_by_side_preserves_page_pairs_searchable_text_and_dimensions(tmp_path):
    original,translated,result=[tmp_path/n for n in ('原文.pdf','translated.pdf','对照.pdf')]
    document(original,'ORIGINAL');document(translated,'TRANSLATED')
    export_pdf(original,translated,result)
    with pymupdf.open(result) as doc:
        assert doc.page_count==2
        assert doc[0].rect.width==640 and doc[0].rect.height==424
        for index,page in enumerate(doc):
            left=page.search_for(f'ORIGINAL {index+1}')[0]
            right=page.search_for(f'TRANSLATED {index+1}')[0]
            assert left.x0 < page.rect.width/2 < right.x0
    assert original.exists() and translated.exists()


def test_export_translation_is_identical_copy_and_blocks_source_overwrite(tmp_path):
    original,translated,result=[tmp_path/n for n in ('a.pdf','b.pdf','copy.pdf')]
    document(original,'a');document(translated,'b')
    export_pdf(original,translated,result,layout='translation')
    assert result.read_bytes()==translated.read_bytes()
    before=original.read_bytes()
    with pytest.raises(ValueError):export_pdf(original,translated,original)
    assert original.read_bytes()==before


def test_failed_export_keeps_existing_file_and_cleans_temporary_file(tmp_path):
    original,translated,result=[tmp_path/n for n in ('a.pdf','b.pdf','existing.pdf')]
    document(original,'a');document(translated,'b',sizes=((300,400),))
    result.write_bytes(b'preserve me')
    with pytest.raises(ValueError,match='页数'):export_pdf(original,translated,result)
    assert result.read_bytes()==b'preserve me'
    assert len(list(tmp_path.iterdir()))==3


def test_empty_and_rotated_pages_are_exportable(tmp_path):
    original,translated,result=[tmp_path/n for n in ('a.pdf','b.pdf','wide.pdf')]
    with pymupdf.open() as doc:
        doc.new_page(width=300,height=400).set_rotation(90)
        doc.save(original);doc.save(translated)
    export_pdf(original,translated,result)
    with pymupdf.open(result) as doc:assert doc[0].rect.width==840 and doc[0].rect.height==324
