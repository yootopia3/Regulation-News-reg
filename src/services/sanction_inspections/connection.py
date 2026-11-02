"""Private runtime configuration and destination checks for the existing AI client."""
import base64
import ipaddress
import os
import re
import socket
from dataclasses import replace
from urllib.parse import urlsplit, urlunsplit

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .models import InspectionError

LAN_NETWORKS = tuple(ipaddress.ip_network(value) for value in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', 'fc00::/7'))
BLOCKED_NETWORKS = tuple(ipaddress.ip_network(value) for value in (
    '0.0.0.0/8', '10.0.0.0/8', '100.64.0.0/10', '127.0.0.0/8', '169.254.0.0/16', '172.16.0.0/12',
    '192.0.0.0/24', '192.0.2.0/24', '192.88.99.0/24', '192.168.0.0/16', '198.18.0.0/15',
    '198.51.100.0/24', '203.0.113.0/24', '224.0.0.0/4', '240.0.0.0/4',
    '2001::/23', '2001:db8::/32', '2002::/16', '3fff::/20'))


def private_allowed(base):
    return base in {item.strip().rstrip('/') for item in os.getenv('AI_CONNECTION_PRIVATE_BASE_URLS', '').split(',') if item.strip()}


def normalize_base(value):
    try:
        if not isinstance(value, str) or not 8 <= len(value) <= 500 or re.search(r'[\s\\%]', value):
            raise ValueError()
        url = urlsplit(value)
        if (not url.hostname or url.hostname.endswith('.') or url.username or url.password or url.query or url.fragment or
                not re.fullmatch(r'[A-Za-z0-9/_-]*', url.path) or
                re.search(r'/(responses|models|chat/completions)/?$', url.path)):
            raise ValueError()
        host = '[' + url.hostname + ']' if ':' in url.hostname else url.hostname
        port = url.port
        authority = host + (':' + str(port) if port and port != (443 if url.scheme == 'https' else 80) else '')
        base = urlunsplit((url.scheme, authority, url.path.rstrip('/'), '', ''))
        if url.scheme != 'https' and not (url.scheme == 'http' and private_allowed(base)):
            raise ValueError()
        return base
    except Exception:
        raise InspectionError('unsafe_ai_url') from None


def allowed_address(address, allow_private=False):
    ip = ipaddress.ip_address(address)
    if allow_private and any(ip in network for network in LAN_NETWORKS):
        return True
    return (ip.version == 4 or ip in ipaddress.ip_network('2000::/3')) and not any(ip in network for network in BLOCKED_NETWORKS)


def destination(base):
    base = normalize_base(base)
    url = urlsplit(base)
    port = url.port or (443 if url.scheme == 'https' else 80)
    try:
        ips = list(dict.fromkeys(item[4][0] for item in socket.getaddrinfo(url.hostname, port, type=socket.SOCK_STREAM)))
    except Exception:
        raise InspectionError('provider_failed') from None
    if not ips or not all(allowed_address(ip, private_allowed(base)) for ip in ips):
        raise InspectionError('unsafe_ai_url')
    if url.scheme == 'http' and not all(any(ipaddress.ip_address(ip) in network for network in LAN_NETWORKS) for ip in ips):
        raise InspectionError('unsafe_ai_url')
    return url, ips[0], port


def decrypt_key(row):
    try:
        key = os.getenv('AI_CONNECTION_ENCRYPTION_KEY', '')
        if not re.fullmatch(r'[a-fA-F0-9]{64}', key):
            raise ValueError()
        version, nonce, tag, ciphertext = row['api_key_ciphertext'].split('.')
        if version != 'v1':
            raise ValueError()
        decode = lambda value: base64.b64decode(value, validate=True)
        if len(decode(nonce)) != 12 or len(decode(tag)) != 16:
            raise ValueError()
        value = AESGCM(bytes.fromhex(key)).decrypt(decode(nonce), decode(ciphertext) + decode(tag),
            ('sanction-ai-connection:v1:' + row['base_url']).encode()).decode()
        if not re.fullmatch(r'[!-~]{8,4096}', value):
            raise ValueError()
        return value
    except Exception:
        raise InspectionError('connection_not_configured') from None


def load_settings(db):
    from .client import Settings
    settings = Settings.from_env()
    if os.getenv('SANCTION_AI_SETTINGS_ENABLED') != 'true':
        return settings
    try:
        if not re.fullmatch(r'[a-fA-F0-9]{64}', os.getenv('AI_CONNECTION_ENCRYPTION_KEY', '')):
            raise ValueError()
        rows = db.table('sanction_ai_connection').select('base_url,protocol,model,api_key_ciphertext,revision').eq('id', True).limit(1).execute().data
        if not rows:
            return settings
        row = rows[0]
        if (row['protocol'] not in ('responses', 'chat_completions') or not re.fullmatch(r'[!-~]{1,200}', row['model']) or
                type(row['revision']) is not int or row['revision'] < 1):
            raise ValueError()
        if normalize_base(row['base_url']) != row['base_url']:
            raise ValueError()
        return replace(settings, base_url=row['base_url'], protocol=row['protocol'], model=row['model'],
                       api_key=decrypt_key(row), connection_revision=row['revision'])
    except Exception:
        raise InspectionError('connection_not_configured') from None


def client_for_db(db):
    from .client import InspectionClient
    return InspectionClient(load_settings(db), settings_loader=lambda: load_settings(db))
