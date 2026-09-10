"""Deterministic article boundaries; headings are candidates, not decisions."""
import re

ARTICLE = re.compile(r'^제\s*(\d+)\s*조(?:\s*의\s*(\d+))?\s*[(（]([^）)]+)[)）]')
BOUNDARY = re.compile(r'^(?:제\s*\d+\s*[장절]|부\s*칙(?:\s|[(（]|$))')
ORGANIZATION = re.compile(r'(?:부|팀|실|센터|지점|본부|위원회)$')
MAX_PARAGRAPHS = 20000
# Keep administrator JSON responses below the hosting response-size ceiling,
# including multibyte Korean text and JSON escaping.
MAX_CHARACTERS = 500_000
MAX_UNITS = 500


def split_articles(paragraphs):
    if len(paragraphs) > MAX_PARAGRAPHS or sum(map(len, paragraphs)) > MAX_CHARACTERS:
        raise ValueError('document_limit')
    units, warnings, seen = [], [], set()
    current = None
    unassigned = []

    def finish(end):
        nonlocal current
        if current is not None:
            current['end_paragraph'] = end
            current['body'] = '\n'.join(paragraphs[current['start_paragraph'] - 1:end])
            units.append(current)
            current = None

    for index, raw in enumerate(paragraphs):
        text = raw.strip()
        match = ARTICLE.match(text)
        if match or BOUNDARY.match(text):
            finish(index)
        if match:
            key = match[1] + (f'-{match[2]}' if match[2] else '')
            if key in seen:
                # Repeated numbering often means a table of contents or appendix.
                # Never merge these silently into a department.
                raise ValueError('unsupported_hwp')
            seen.add(key)
            heading = match[3].strip()
            deleted = bool(re.search(r'삭\s*제', heading)) or bool(re.match(r'\s*삭\s*제', text[match.end():]))
            current = {'article_key': key, 'heading': heading, 'department': heading if ORGANIZATION.search(heading) and not deleted else '', 'start_paragraph': index + 1}
            if deleted:
                warnings.append(f'제{key}조: 삭제 표시를 확인하세요. 소관부서 후보에서 제외했습니다.')
        elif current is None and text and not BOUNDARY.match(text):
            unassigned.append((index + 1, text))
    finish(len(paragraphs))
    if not units:
        raise ValueError('unsupported_hwp')
    if len(units) > MAX_UNITS:
        raise ValueError('document_limit')
    if unassigned:
        # Administrator-only evidence, never logged or sent to general users.
        warnings.append('조문 밖 문단 — 목차·개정 이력·별첨 여부를 확인하세요.\n' + '\n'.join(f'{i}: {t}' for i, t in unassigned))
    warnings.append('부서명은 조문 제목에서 찾은 후보입니다. 공통업무·교차참조와 하위 조직을 원본에서 확인하세요.')
    return {'units': units, 'warnings': warnings}
