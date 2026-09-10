"""Isolated HWP v5 parser process. Writes only a private result file."""
import json
import os
import sys
import zlib
from pathlib import Path

from .structure import split_articles

MAX_EXPANDED = 32 * 1024 * 1024


def deny_network(event, args):
    # Audit hooks preserve socket's type, which ssl subclasses during imports.
    if event in ('socket.__new__', 'socket.connect', 'socket.bind', 'socket.getaddrinfo', 'socket.gethostbyname'):
        raise RuntimeError('network_disabled')


def expanded_stream(data, compressed, remaining):
    if not compressed:
        if len(data) > remaining:
            raise ValueError('document_limit')
        return len(data)
    decoder = zlib.decompressobj(-15)
    result = decoder.decompress(data, remaining + 1)
    if len(result) > remaining or decoder.unconsumed_tail:
        raise ValueError('document_limit')
    if not decoder.eof:
        raise ValueError('invalid_hwp')
    return len(result)


def extract(path):
    import io
    import olefile
    from hwp5.xmlmodel import Hwp5File
    from lxml import etree

    if Path(path).stat().st_size > 2 * 1024 * 1024:
        raise ValueError('document_limit')
    with olefile.OleFileIO(path) as ole:
        header = ole.openstream('FileHeader').read()
        if len(header) < 40 or not header.startswith(b'HWP Document File') or header[35] != 5:
            raise ValueError('invalid_hwp')
        flags = int.from_bytes(header[36:40], 'little')
        if flags & 2:
            raise ValueError('encrypted_hwp')
        if flags & (4 | 16):
            raise ValueError('unsupported_hwp')
        remaining = MAX_EXPANDED
        for name in ole.listdir():
            # Embedded binaries are never converted (embedbin=False). Their
            # per-item compression flags differ from the document-wide flag.
            if name[0] in ('BodyText', 'DocInfo'):
                remaining -= expanded_stream(ole.openstream(name).read(), bool(flags & 1), remaining)
    doc = Hwp5File(path)
    result = io.BytesIO()
    try:
        doc.xmlevents(embedbin=False).dump(result)
    finally:
        doc.close()
    if result.tell() > MAX_EXPANDED:
        raise ValueError('document_limit')
    root = etree.fromstring(result.getvalue(), parser=etree.XMLParser(resolve_entities=False, no_network=True))
    paragraphs = []
    for p in root.xpath('//BodyText//Paragraph'):
        paragraphs.append(''.join(n.text or '' for n in p.xpath('.//Text') if n.xpath('ancestor::Paragraph[1]')[0] is p).strip())
    return split_articles(paragraphs)


def main():
    if os.name == 'posix':
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
        resource.setrlimit(resource.RLIMIT_CPU, (45, 45))
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_EXPANDED,) * 2)
    sys.addaudithook(deny_network)
    # Do not allow provider credentials to reach parser dependencies.
    allowed_errors = {'document_limit', 'invalid_hwp', 'encrypted_hwp', 'unsupported_hwp'}
    try:
        result = extract(sys.argv[1])
    except Exception as error:
        result = {'error': str(error) if isinstance(error, ValueError) and str(error) in allowed_errors else 'parser_failed'}
    Path(sys.argv[2]).write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    main()
