"""Invoked only by the secret-free, time-limited subprocess runner."""
import json
from pathlib import Path
import sys


def extract(path):
    from pypdf import PdfReader
    if Path(path).stat().st_size > 10 * 1024 * 1024:
        return {'error': 'pdf_limit'}
    reader = PdfReader(path, strict=True)
    if reader.is_encrypted:
        return {'error': 'encrypted_pdf'}
    if not 1 <= len(reader.pages) <= 200:
        return {'error': 'pdf_limit'}
    pages, total = [], 0
    for number, page in enumerate(reader.pages, 1):
        # A text header is not proof that an image-only body was extracted.
        # Until OCR is connected, even logo-bearing pages require manual review.
        if len(page.images):
            return {'error': 'ocr_required'}
        text = (page.extract_text() or '').strip()
        # Mixed scanned/text PDFs must not silently lose findings.
        if len(text) < 20:
            return {'error': 'ocr_required'}
        total += len(text)
        if len(text) > 12000 or total > 80000:
            return {'error': 'pdf_limit'}
        pages.append({'number': number, 'text': text})
    return {'pages': pages}


def main():
    if sys.platform != 'win32':
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
        resource.setrlimit(resource.RLIMIT_CPU, (45, 45))
    def no_network(event, args):
        if event.startswith('socket.'):
            raise RuntimeError('network_disabled')
    sys.addaudithook(no_network)
    try:
        result = extract(sys.argv[1])
    except Exception:
        result = {'error': 'invalid_pdf'}
    Path(sys.argv[2]).write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    main()
