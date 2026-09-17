"""FSS-only, certificate-verified downloads with DNS addresses pinned per hop."""
import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import urljoin, urlsplit

from src.config.settings import USER_AGENT
from .models import InspectionError

MAX_PDF_BYTES = 10 * 1024 * 1024
HOSTS = {'www.fss.or.kr', 'fss.or.kr'}


def destination(url):
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.hostname not in HOSTS or parsed.username or
                parsed.password or parsed.port not in (None, 443) or any(ord(c) < 33 for c in url)):
            raise ValueError()
        addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        ips = list(dict.fromkeys(item[4][0] for item in addresses))
        if not ips or not all(ipaddress.ip_address(ip).is_global for ip in ips):
            raise ValueError()
        return parsed.hostname, ips[0], (parsed.path or '/') + ('?' + parsed.query if parsed.query else '')
    except Exception:
        raise InspectionError('unsafe_pdf_url') from None


def download_pdf(url):
    deadline = time.monotonic() + 60
    try:
        for _ in range(4):
            host, ip, path = destination(url)
            connection = http.client.HTTPSConnection(host, timeout=10)
            try:
                # No second DNS lookup: pin the validated IP, while preserving SNI/certificate checks.
                raw = socket.create_connection((ip, 443), timeout=10)
                try:
                    connection.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
                except Exception:
                    raw.close()
                    raise
                connection.request('GET', path, headers={'Host': host, 'User-Agent': USER_AGENT, 'Accept': 'application/pdf', 'Accept-Encoding': 'identity'})
                response = connection.getresponse()
                if response.status in (301, 302, 303, 307, 308):
                    location = response.getheader('Location')
                    if not location:
                        raise InspectionError('pdf_download_failed')
                    url = urljoin(url, location)
                    continue
                if response.status != 200:
                    raise InspectionError('pdf_download_failed')
                chunks, size = [], 0
                while True:
                    if time.monotonic() > deadline:
                        raise InspectionError('pdf_download_timeout')
                    chunk = response.read1(65536)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_PDF_BYTES:
                        raise InspectionError('pdf_limit')
                    chunks.append(chunk)
                data = b''.join(chunks)
                if not data.startswith(b'%PDF-'):
                    raise InspectionError('invalid_pdf')
                return data
            finally:
                connection.close()
        raise InspectionError('pdf_redirect_limit')
    except InspectionError:
        raise
    except Exception:
        raise InspectionError('pdf_download_failed') from None
