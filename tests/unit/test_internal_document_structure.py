import pytest

from src.services.internal_documents.structure import split_articles


def test_department_boundaries_preserve_subitems_and_stop_at_chapter():
    result = split_articles(['개정 이력', '제1장 총칙', '제1조(가상업무부) 담당 업무', '1. 고객 통지', '가. 발송 실패 확인', '제2조(가상전산팀) 담당 업무', '1. 시스템 운영', '부칙', '1. 시행일'])
    first, second = result['units']
    assert first['department'] == '가상업무부'
    assert '발송 실패' in first['body']
    assert '시스템 운영' not in first['body']
    assert second['department'] == '가상전산팀'
    assert '시행일' not in second['body']
    assert any('시행일' in w for w in result['warnings'])
    assert first['end_paragraph'] < second['start_paragraph']


def test_deleted_and_common_articles_have_no_department():
    result = split_articles(['제1조(목적) 공통 사항', '제2조(가상지원부) 삭제', '제3조의2(가상관리팀) 업무', '1. 제1조 참조'])
    assert [u['department'] for u in result['units']] == ['', '', '가상관리팀']
    assert result['units'][2]['article_key'] == '3-2'
    assert '제1조 참조' in result['units'][2]['body']
    assert any('삭제' in w for w in result['warnings'])


@pytest.mark.parametrize('paragraphs,code', [
    (['제1조(가상업무부)', '1. 처리', '제1조(가상지원부)'], 'unsupported_hwp'),
    (['아무 조문도 없음'], 'unsupported_hwp'),
    (['x' * 2_000_001], 'document_limit'),
])
def test_ambiguous_and_excessive_documents_fail_closed(paragraphs, code):
    with pytest.raises(ValueError, match=code):
        split_articles(paragraphs)
