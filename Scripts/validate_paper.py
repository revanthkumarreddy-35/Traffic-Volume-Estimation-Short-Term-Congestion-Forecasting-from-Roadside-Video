"""Check the current DOCX/PDF against the requested edits and verified tables."""
from datetime import date
import hashlib
import json
from pathlib import Path
import re

import fitz
from docx import Document
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT/'Documents/Research paper.docx'
PDF = PAPER.with_suffix('.pdf')
ANALYSIS = ROOT/'CP-1/Forecasting_v3_Results/Expanded_Analysis/yolo11/expanded_01'


def main():
    doc = Document(PAPER)
    source = Document(ROOT/'Documents/Paper_Sources/Research paper_updated_authors.docx')
    paragraphs = [p.text for p in doc.paragraphs]
    body = '\n'.join(paragraphs)
    with fitz.open(PDF) as pdf:
        text = '\n'.join(p.get_text() for p in pdf)
        for removed in ['Keywords:', 'Declarations', 'The remainder of the paper is organised as follows']:
            assert removed not in body and removed not in text, removed
        for name in ['Puligadda Charishma','Althi Bhargavi','Nossam Revanth Kumar Reddy',
                     'Alavalapati Naga Thanmai','Dr. T. Praveen']:
            assert name in body and name in text, name
        assert len(doc.inline_shapes) == len(source.inline_shapes) == 5
        assert len(doc._element.xpath('.//m:oMath')) == len(source._element.xpath('.//m:oMath')) == 51
        assert len(doc.tables) == len(source.tables)+1 == 13
        figures = [int(re.match(r'^Figure (\d+)\.',p)[1]) for p in paragraphs if re.match(r'^Figure \d+\.',p)]
        tables = [re.match(r'^Table (A?\d+)\.',p)[1] for p in paragraphs if re.match(r'^Table A?\d+\.',p)]
        assert figures == [1,2,3,4,5]
        assert tables == [str(i) for i in range(1,12)]+['A1']
        assert len(doc.tables[0].columns) == 1
        abstract_index = [p.text for p in source.paragraphs].index('Abstract')
        abstract = source.paragraphs[abstract_index+1].text
        assert doc.tables[0].cell(0,0).paragraphs[1].text == abstract
        for headline in ['37.5%', '50.0%', '40.625%', '71.875%', '81.25%', '0.4283']:
            assert headline in text, headline
        integration = json.loads((ANALYSIS/'PAPER_INTEGRATION.json').read_text(encoding='utf-8'))
        data_rows = [[[c.text for c in row.cells] for row in table.rows[1:]] for table in doc.tables[1:]]
        for key in ['protocol_rows','cached_comparison_rows','expanded_class_rows','expanded_method_rows']:
            expected = [[str(value) for value in row] for row in integration[key]]
            assert expected in data_rows, key
        bookmarks = {b.get(qn('w:name')) for b in doc._element.xpath('.//w:bookmarkStart')}
        links = doc._element.xpath('.//w:hyperlink[@w:anchor]')
        assert all(h.get(qn('w:anchor')) in bookmarks for h in links)
        for kind, identifiers in [('ref',range(1,27)),('figure',range(1,6)),('table',list(range(1,12))+['A1'])]:
            assert all(f'cp1_{kind}_{i}' in bookmarks for i in identifiers)
        external = doc._element.xpath('.//w:hyperlink[@r:id]')
        assert len(external) == 26
        uris = {doc.part.rels[h.get(qn('r:id'))].target_ref for h in external}
        internal_pdf, external_pdf = [], []
        for page in pdf:
            for link in page.get_links():
                if link['kind'] == fitz.LINK_GOTO:
                    assert 0 <= link['page'] < len(pdf)
                    internal_pdf.append(link)
                elif link['kind'] == fitz.LINK_URI:
                    external_pdf.append(link)
        assert len(internal_pdf) >= len(links)
        assert uris <= {link['uri'] for link in external_pdf}
        # Preserve the exact numeric meaning of the current experiment tables.
        report = dict(verified_date=date.today().isoformat(),pdf_pages=len(pdf),
                      preserved_equations=51,figures=5,research_tables=12,
                      reference_source_links=26,internal_pdf_links=len(internal_pdf),
                      external_pdf_links=len(external_pdf),all_internal_links_resolve=True,
                      abstract_layout='full width, no keywords sidebar',abstract_text_preserved=True,
                      outline_paragraph_removed=True,declarations_removed=True,
                      figure_numbers_in_reading_order=True,
                      new_tables_match_integration_record=True,
                      process_explained_in='Section 3.11 and Figure 5',
                      comparisons_in='Sections 4.6-4.8 and Tables 8-11',
                      docx_sha256=hashlib.sha256(PAPER.read_bytes()).hexdigest(),
                      pdf_sha256=hashlib.sha256(PDF.read_bytes()).hexdigest())
    (ANALYSIS/'PAPER_VALIDATION.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('PASS:',report['pdf_pages'],'pages; 5 figures, 12 research tables, 51 equations, 26 source links.')
    print('Author names, requested removals, full-width abstract and cross-reference destinations verified.')


if __name__ == '__main__':
    main()
