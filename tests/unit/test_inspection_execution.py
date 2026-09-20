import io
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.services.sanction_inspections.download import destination
from src.services.sanction_inspections.models import InspectionError
from src.services.sanction_inspections.worker import run_once


@pytest.mark.parametrize('url', ['http://www.fss.or.kr/a', 'https://www.fss.or.kr.evil.test/a',
                                'https://user@www.fss.or.kr/a', 'https://127.0.0.1/a', 'https://www.fss.or.kr:444/a'])
def test_download_rejects_unapproved_url(url):
    with pytest.raises(InspectionError, match='unsafe_pdf_url'):
        destination(url)


def test_dns_rebinding_and_mixed_private_addresses_are_rejected(monkeypatch):
    monkeypatch.setattr('socket.getaddrinfo', lambda *a, **k: [(None, None, None, None, ('127.0.0.1', 443))])
    with pytest.raises(InspectionError, match='unsafe_pdf_url'):
        destination('https://www.fss.or.kr/a')
    monkeypatch.setattr('socket.getaddrinfo', lambda *a, **k: [(None, None, None, None, ('8.8.8.8', 443))])
    assert destination('https://www.fss.or.kr/a?file=1') == ('www.fss.or.kr', '8.8.8.8', '/a?file=1')


def test_real_pdf_extract_preserves_pages_and_isolated_runner(tmp_path):
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    from src.services.internal_documents.worker import parse_isolated
    writer = PdfWriter()
    for text in ['First finding: credit approval was missing.', 'Second finding: evidence retention was missing.']:
        page = writer.add_blank_page(612, 792)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
        stream = DecodedStreamObject(); stream.set_data(f'BT /F1 12 Tf 72 720 Td ({text}) Tj ET'.encode())
        page[NameObject('/Contents')] = stream
    output = io.BytesIO(); writer.write(output)
    result = parse_isolated(output.getvalue(), module='src.services.sanction_inspections.pdf_parser', suffix='.pdf')
    assert [page['number'] for page in result['pages']] == [1, 2]
    assert 'First finding' in result['pages'][0]['text']
    assert 'Second finding' in result['pages'][1]['text']


def test_blank_pdf_requires_ocr(tmp_path):
    from pypdf import PdfWriter
    from src.services.sanction_inspections.pdf_parser import extract
    writer = PdfWriter(); writer.add_blank_page(612, 792)
    path = tmp_path / 'blank.pdf'; writer.write(path)
    assert extract(path) == {'error': 'ocr_required'}


def test_scanned_body_with_selectable_header_requires_ocr(tmp_path, monkeypatch):
    from src.services.sanction_inspections.pdf_parser import extract
    page = SimpleNamespace(images=['scanned-body'], extract_text=lambda: 'This selectable header alone exceeds twenty characters.')
    monkeypatch.setattr('pypdf.PdfReader', lambda *a, **k: SimpleNamespace(is_encrypted=False, pages=[page]))
    path = tmp_path / 'mixed.pdf'; path.write_bytes(b'%PDF-fixture')
    assert extract(path) == {'error': 'ocr_required'}


def test_worker_failure_finishes_without_saving_provider_exception():
    db = Mock()
    job = {'id': 'job', 'article_id': 'article', 'lease_token': 'lease', 'versions': {}}
    db.rpc.return_value.execute.return_value.data = job
    db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
        'agency': 'FSS_SANCTION', 'category': 'sanction_notice', 'analysis_result': {'pdf_url': 'https://www.fss.or.kr/a'}}
    downloader = Mock(side_effect=RuntimeError('PRIVATE_CANARY'))
    assert run_once(db, Mock(), downloader=downloader)
    finish = db.rpc.call_args.args
    assert finish[0] == 'inspection_finish'
    assert finish[1]['p_error'] == 'inspection_failed'
    assert finish[1]['p_result'] is None
    assert 'PRIVATE_CANARY' not in str(finish)


def test_disabled_worker_does_not_claim():
    db, client = Mock(), Mock()
    client.settings.check.side_effect = InspectionError('disabled')
    with pytest.raises(InspectionError):
        run_once(db, client)
    db.rpc.assert_not_called()


def test_worker_connects_trusted_pdf_and_database_units_to_private_finish(monkeypatch):
    monkeypatch.setattr('src.services.sanction_inspections.worker.load_master', lambda *_: None)
    db, client = Mock(), Mock()
    versions = {'doc': 1}
    job = {'id': 'job', 'article_id': 'article', 'lease_token': 'lease', 'versions': versions}
    db.rpc.side_effect = lambda name, args: SimpleNamespace(execute=lambda: SimpleNamespace(data=job if name == 'inspection_claim' else versions))
    article_query, units_query, doc_query = Mock(), Mock(), Mock()
    for query in (article_query, units_query, doc_query):
        for method in ('select', 'eq', 'single', 'order', 'range'):
            getattr(query, method).return_value = query
    article_query.execute.return_value.data = {'agency': 'FSS_SANCTION', 'category': 'sanction_notice', 'analysis_result': {'pdf_url': 'https://www.fss.or.kr/a'}}
    units_query.execute.return_value.data = [{'article_key': '1', 'department': 'Synthetic team', 'body': 'Synthetic duty', 'reviewed': True}]
    doc_query.execute.return_value.data = {'document_kind': 'organization', 'status': 'active', 'revision': 1}
    db.table.side_effect = lambda name: article_query if name == 'articles' else doc_query if name == 'internal_documents' else units_query
    engine = Mock(return_value={'status': 'needs_review', 'document_versions': versions})
    monkeypatch.setattr('src.services.sanction_inspections.worker.analyze', engine)
    downloader = Mock(return_value=b'%PDF-fixture')
    parser = Mock(return_value={'pages': [{'number': 1, 'text': 'Synthetic public finding evidence'}]})
    assert run_once(db, client, downloader, parser)
    downloader.assert_called_once_with('https://www.fss.or.kr/a')
    assert engine.call_args.args[1][0].reviewed is True
    assert db.rpc.call_args.args[0] == 'inspection_finish'
    assert db.rpc.call_args.args[1]['p_result']['status'] == 'needs_review'
    assert db.rpc.call_args.args[1]['p_error'] is None


def test_download_checks_redirect_destination_and_stream_limit(monkeypatch):
    from src.services.sanction_inspections import download
    monkeypatch.setattr('socket.getaddrinfo', lambda *a, **k: [(None, None, None, None, ('8.8.8.8', 443))])
    monkeypatch.setattr('socket.create_connection', Mock())
    monkeypatch.setattr('ssl.create_default_context', Mock())
    response = Mock(status=302)
    response.getheader.return_value = 'https://127.0.0.1/private'
    connection = Mock(); connection.getresponse.return_value = response
    monkeypatch.setattr('http.client.HTTPSConnection', Mock(return_value=connection))
    with pytest.raises(InspectionError, match='unsafe_pdf_url'):
        download.download_pdf('https://www.fss.or.kr/a')
    response.status = 200
    response.read1.side_effect = [b'%PDF-oversize', b'']
    monkeypatch.setattr(download, 'MAX_PDF_BYTES', 5)
    with pytest.raises(InspectionError, match='pdf_limit'):
        download.download_pdf('https://www.fss.or.kr/a')


def test_download_identifies_client_for_fss_pdf_endpoint(monkeypatch):
    from src.services.sanction_inspections import download
    monkeypatch.setattr('socket.getaddrinfo', lambda *a, **k: [(None, None, None, None, ('8.8.8.8', 443))])
    monkeypatch.setattr('socket.create_connection', Mock())
    monkeypatch.setattr('ssl.create_default_context', Mock())
    connection = Mock()

    def response_for_request():
        headers = connection.request.call_args.kwargs['headers']
        body = b'%PDF-fixture' if headers.get('User-Agent') else b'<script>File Not Found</script>'
        response = Mock(status=200)
        response.read1.side_effect = [body, b'']
        return response

    connection.getresponse.side_effect = response_for_request
    monkeypatch.setattr('http.client.HTTPSConnection', Mock(return_value=connection))
    assert download.download_pdf('https://www.fss.or.kr/a') == b'%PDF-fixture'
