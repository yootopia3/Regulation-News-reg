"""Verified offline import and explicit archive refresh. No network access."""
import hashlib
import io
import json
import re
import uuid
import zipfile
from urllib.parse import parse_qs, urlsplit
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import insert, select, text, update
from .agency_policy import EXCLUDED_AGENCY, is_excluded
from .database import (articles, article_sources, historical_records, history_imports,
                       historical_files, historical_article_files)

HISTORY_ROOT = Path(__file__).resolve().parents[1] / 'history-data'
TABLES = ('articles', 'sanction_publications', 'sanction_inspections')
ANALYSIS_FIELDS = ('summary', 'importance_score', 'risk_level', 'impact_analysis',
                   'action_items', 'keywords', 'detailed_report', 'report_generated_at')


def require(condition):
    if not condition:
        raise ValueError('Invalid historical dataset')


def identifier(value):
    require(isinstance(value, str) and str(uuid.UUID(value)) == value)
    return value


def instant(value):
    require(isinstance(value, str))
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None)
    return result.astimezone(timezone.utc)


def read_snapshot(root):
    manifest_data = (root / 'manifest.json').read_bytes()
    require(len(manifest_data) <= 1024 * 1024)
    manifest = json.loads(manifest_data)
    require(manifest.get('format') == 'regulation-history-v1')
    require(re.fullmatch(r'[a-z0-9]{20}', manifest.get('source_project', '')) is not None)
    require(set(manifest['files']) == set(TABLES))
    batches = {}
    total = 0
    for name in TABLES:
        spec = manifest['files'][name]
        require(spec['name'] == name + '.jsonl')
        path = root / spec['name']
        require(path.stat().st_size == spec['bytes'] and 0 <= spec['bytes'] <= 64 * 1024 * 1024)
        total += spec['bytes']
        require(total <= 64 * 1024 * 1024)
        data = path.read_bytes()
        require(hashlib.sha256(data).hexdigest() == spec['sha256'])
        batch, keys = [], set()
        for line in data.splitlines():
            require(0 < len(line) <= 4 * 1024 * 1024)
            raw = line.decode('utf-8')
            record = json.loads(raw)
            require(isinstance(record, dict))
            key = identifier(record['inspection_id'] if name == 'sanction_publications' else record['id'])
            require(key not in keys)
            keys.add(key)
            article_id = key if name == 'articles' else identifier(record['article_id'])
            if name == 'sanction_inspections':
                require(not {'created_by', 'lease_token', 'lease_until', 'request_id'}.intersection(record))
            batch.append(dict(source_table=name, source_id=key, article_id=article_id,
                              payload=raw, payload_sha256=hashlib.sha256(line).hexdigest(), record=record))
        require(len(batch) == spec['rows'] and len(batch) <= 100000)
        batches[name] = batch
    article_ids = {row['article_id'] for row in batches['articles']}
    inspections = {row['source_id']: row['article_id'] for row in batches['sanction_inspections']}
    require(all(row['article_id'] in article_ids for name in TABLES for row in batches[name]))
    require(all(inspections.get(row['source_id']) == row['article_id'] for row in batches['sanction_publications']))
    binaries, associations, pairs = {}, [], set()
    for spec in manifest.get('original_files', []):
        digest, extension = spec['sha256'], spec['extension']
        require(re.fullmatch(r'[0-9a-f]{64}', digest) is not None)
        require(extension in {'pdf', 'hwp', 'hwpx'})
        require(spec['file'] == 'pdfs/' + digest + '.' + extension)
        path = root / spec['file']
        require(path.stat().st_size == spec['bytes'] and 0 < spec['bytes'] <= 32 * 1024 * 1024)
        require(isinstance(spec['source_url'], str) and len(spec['source_url']) <= 4000)
        if digest not in binaries:
            content = path.read_bytes()
            total += len(content)
            require(total <= 512 * 1024 * 1024)
            require(hashlib.sha256(content).hexdigest() == digest)
            if extension == 'pdf':
                require(content.startswith(b'%PDF-'))
            elif extension == 'hwp':
                require(content.startswith(bytes.fromhex('d0cf11e0a1b11ae1')))
            else:
                with zipfile.ZipFile(io.BytesIO(content)) as archive:
                    require(archive.getinfo('mimetype').file_size <= 128)
                    require(archive.read('mimetype').strip() == b'application/hwp+zip')
            binaries[digest] = dict(sha256=digest, extension=extension, content=content, size=len(content))
        for article_id in spec['article_ids']:
            require(identifier(article_id) in article_ids)
            if (article_id, digest) not in pairs:
                pairs.add((article_id, digest))
                associations.append(dict(article_id=article_id, file_sha256=digest, source_url=spec['source_url']))
    return manifest_data, manifest, batches, binaries, associations


def allowed_snapshot(batches, binaries, associations):
    """Exclude an agency and its dependent records even in an older input bundle."""
    excluded = {row['article_id'] for row in batches['articles'] if is_excluded(row['record'].get('agency'))}
    batches = {name: [row for row in rows if row['article_id'] not in excluded] for name, rows in batches.items()}
    associations = [row for row in associations if row['article_id'] not in excluded]
    used = {row['file_sha256'] for row in associations}
    binaries = {key: row for key, row in binaries.items() if key in used}
    return batches, binaries, associations


def verify_retained_snapshot(conn, source_system, batches, binaries, associations):
    """A removal-only bundle may acknowledge unchanged retained records, never merge."""
    ids = select(article_sources.c.article_id).where(article_sources.c.source_system == source_system)
    expected = {(row['source_table'], row['source_id']): row['payload'] for rows in batches.values() for row in rows}
    actual = {(row['source_table'], row['source_id']): row['payload']
              for row in conn.execute(select(historical_records).where(historical_records.c.article_id.in_(ids))).mappings()}
    require(actual == expected)
    actual_links = {(row['article_id'], row['file_sha256'], row['source_url'])
                    for row in conn.execute(select(historical_article_files)
                        .where(historical_article_files.c.article_id.in_(ids))).mappings()}
    require(actual_links == {(r['article_id'], r['file_sha256'], r['source_url']) for r in associations})
    require(set(conn.execute(ids).scalars()) == {r['article_id'] for r in batches['articles']})
    for digest in binaries:
        content = conn.execute(select(historical_files.c.content).where(historical_files.c.sha256 == digest)).scalar_one()
        require(hashlib.sha256(content).hexdigest() == digest)


def article_values(row):
    record = row['record']
    require(isinstance(record['title'], str) and 0 < len(record['title']) <= 1000)
    require(record['category'] in {'press_release', 'regulation_notice', 'sanction_notice'})
    require(record['content'] is None or isinstance(record['content'], str))
    require(record['agency'] is None or isinstance(record['agency'], str) and len(record['agency']) <= 40)
    published = instant(record['published_at']).isoformat() if record.get('published_at_source') == 'source' else None
    return dict(id=row['article_id'], title=record['title'], body=record['content'] or '',
        category=record['category'], agency=record['agency'], published_at=published,
        source_version='archive:' + row['payload_sha256'], is_demo=False)


def import_snapshot(engine, root=HISTORY_ROOT):
    manifest_data, manifest, batches, binaries, associations = read_snapshot(root)
    batches, binaries, associations = allowed_snapshot(batches, binaries, associations)
    snapshot_id = hashlib.sha256(manifest_data).hexdigest()
    source_system = 'internet-platform:' + manifest['source_project']
    with engine.begin() as conn:
        if engine.dialect.name == 'postgresql':
            conn.execute(text('SELECT pg_advisory_xact_lock(77461023)'))
        existing = conn.execute(select(history_imports.c.snapshot_id).where(history_imports.c.snapshot_id == snapshot_id)).first()
        if existing:
            return False
        installed = conn.execute(select(history_imports.c.snapshot_id)
            .where(history_imports.c.source_system == source_system)).scalar_one_or_none()
        if installed:
            if 'refresh' in manifest:
                from .history_refresh import refresh
                return refresh(conn, installed, source_system, manifest_data, manifest, batches, binaries, associations)
            exclusion = manifest.get('exclusion', {})
            if exclusion != {'parent_snapshot_id': installed, 'agencies': [EXCLUDED_AGENCY]}:
                raise ValueError('A historical snapshot from this source is already installed')
            verify_retained_snapshot(conn, source_system, batches, binaries, associations)
            conn.execute(update(history_imports).where(history_imports.c.snapshot_id == installed)
                .values(snapshot_id=snapshot_id, manifest=manifest_data.decode('utf-8'),
                    article_count=len(batches['articles']), record_count=sum(map(len, batches.values()))))
            return False
        for row in batches['articles']:
            record = row['record']
            received = instant(record['created_at'])
            conn.execute(insert(articles).values(**article_values(row)))
            conn.execute(insert(article_sources).values(article_id=row['article_id'], source_system=source_system,
                source_id=row['source_id'], source_url=record['link'], received_at=received, source_updated_at=None))
        for name in TABLES:
            for row in batches[name]:
                conn.execute(insert(historical_records).values(**{k: v for k, v in row.items() if k != 'record'}))
        for row in binaries.values():
            conn.execute(insert(historical_files).values(**row))
        if associations:
            conn.execute(insert(historical_article_files), associations)
        from .features import bootstrap_connection
        bootstrap_connection(conn)
        conn.execute(insert(history_imports).values(snapshot_id=snapshot_id, source_system=source_system,
            article_count=len(batches['articles']), record_count=sum(map(len, batches.values())),
            manifest=manifest_data.decode('utf-8')))
    return True


def sanction_source_key(agency, source_url):
    """Match FSS notice identities, ignoring search dates in duplicate source URLs."""
    if agency not in ('FSS_SANCTION', 'FSS_MGMT_NOTICE') or not source_url:
        return None
    try:
        url = urlsplit(source_url)
        if (url.scheme not in ('http', 'https') or url.hostname not in ('fss.or.kr', 'www.fss.or.kr')
                or url.username or url.password or url.port
                or url.path not in ('/fss/job/openInfo/view.do', '/fss/job/openInfo/inspectionDetail.do')):
            return None
        query = parse_qs(url.query)
        keys = [query.get(name, []) for name in ('examMgmtNo', 'emOpenSeq')]
        if any(len(values) != 1 or not re.fullmatch(r'[0-9]+', values[0]) for values in keys):
            return None
        return agency, keys[0][0], keys[1][0]
    except ValueError:
        return None


def publication_alias(conn, article_id):
    from .database import publications
    source = articles.join(article_sources)
    requested = conn.execute(select(articles.c.agency, article_sources.c.source_url)
        .select_from(source).where(articles.c.id == article_id,
            articles.c.category == 'sanction_notice')).mappings().first()
    key = sanction_source_key(**requested) if requested else None
    if key is None:
        return None
    candidates = conn.execute(select(publications, articles.c.agency, article_sources.c.source_url)
        .select_from(source.join(publications, publications.c.article_id == articles.c.id))
        .where(articles.c.category == 'sanction_notice', articles.c.agency == requested['agency'],
            publications.c.status == 'published', articles.c.id != article_id)
        .order_by(publications.c.published_at.desc(), publications.c.inspection_id)).mappings()
    return next((row for row in candidates if sanction_source_key(row['agency'], row['source_url']) == key), None)


def saved_report(conn, article_id):
    result = dict(analysis=None, published_report=None, published_at=None, publication_source=None)
    rows = conn.execute(select(historical_records.c.source_table, historical_records.c.payload).where(
        historical_records.c.article_id == article_id,
        historical_records.c.source_table.in_(('articles', 'sanction_publications')))).mappings()
    for row in rows:
        record = json.loads(row['payload'])
        if row['source_table'] == 'articles':
            analysis = record.get('analysis_result')
            if isinstance(analysis, dict):
                result['analysis'] = {key: analysis[key] for key in ANALYSIS_FIELDS if analysis.get(key) is not None} or None
        elif record.get('status') == 'published':
            result['published_report'] = record.get('report')
            result['published_at'] = record.get('published_at')
            result['publication_source'] = record.get('publication_source') or 'manual'
    from .database import publications
    live = conn.execute(select(publications).where(publications.c.article_id == article_id)).mappings().first()
    # An explicit local withdrawal wins over historical and duplicate records.
    if not live and not result['published_report']:
        live = publication_alias(conn, article_id)
    if live:
        result['published_report'] = json.loads(live['report']) if live['status'] == 'published' else None
        result['published_at'] = live['published_at'] if live['status'] == 'published' else None
        result['publication_source'] = live['publication_source'] if live['status'] == 'published' else None
    return result
