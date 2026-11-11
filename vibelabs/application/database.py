"""Versioned schema. All statements use bound parameters through SQLAlchemy."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (MetaData, Table, Column, String, Integer, Text, Boolean, LargeBinary,
                        ForeignKey, UniqueConstraint, CheckConstraint, DateTime, Index, func,
                        create_engine, select, insert, event)
from sqlalchemy.pool import StaticPool

metadata = MetaData()
versions = Table("schema_versions", metadata, Column("version", Integer, primary_key=True))
posts = Table("board_posts", metadata,
    Column("id", String(36), primary_key=True), Column("author_name", String(40), nullable=False),
    Column("title", String(150), nullable=False), Column("body", Text, nullable=False),
    Column("category", String(20), nullable=False), Column("status", String(20), nullable=False, index=True),
    Column("is_pinned", Boolean, nullable=False), Column("password_hash", String(180), nullable=False),
    Column("revision", Integer, nullable=False), Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False), Column("published_at", String(40)))
attachments = Table("board_attachments", metadata,
    Column("id", String(36), primary_key=True),
    Column("post_id", ForeignKey("board_posts.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("name", String(180), nullable=False), Column("size", Integer, nullable=False),
    Column("content", LargeBinary, nullable=False))
comments = Table("board_comments", metadata,
    Column("id", String(36), primary_key=True),
    Column("post_id", ForeignKey("board_posts.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("author_name", String(40), nullable=False), Column("body", Text, nullable=False),
    Column("password_hash", String(180), nullable=False), Column("revision", Integer, nullable=False),
    Column("created_at", String(40), nullable=False), Column("updated_at", String(40), nullable=False))
limits = Table("request_limits", metadata, Column("key", String(100), primary_key=True),
               Column("window", Integer, nullable=False), Column("count", Integer, nullable=False))
articles = Table("regulatory_articles", metadata,
    Column("id", String(36), primary_key=True), Column("title", String(1000), nullable=False),
    Column("body", Text, nullable=False), Column("category", String(30), nullable=False, index=True),
    Column("agency", String(40)), Column("published_at", String(40)),
    Column("source_version", String(128), nullable=False), Column("is_demo", Boolean, nullable=False))
# Source identity is separate from public article fields. It is not an API contract
# with the upstream system; its exact field mapping is agreed during integration.
article_sources = Table("regulatory_article_sources", metadata,
    Column("article_id", ForeignKey("regulatory_articles.id", ondelete="CASCADE"), primary_key=True),
    Column("source_system", String(100), nullable=False),
    Column("source_id", String(256), nullable=False),
    Column("source_url", Text),
    Column("received_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("source_updated_at", DateTime(timezone=True)),
    UniqueConstraint("source_system", "source_id", name="uq_regulatory_article_source_key"),
    CheckConstraint("length(trim(source_system)) > 0", name="ck_article_source_system_nonempty"),
    CheckConstraint("length(trim(source_id)) > 0", name="ck_article_source_id_nonempty"))
article_list_indexes = (
    Index("ix_articles_published_id", articles.c.published_at.desc(), articles.c.id),
    Index("ix_articles_category_published_id", articles.c.category, articles.c.published_at.desc(), articles.c.id),
)
admins = Table("local_admins", metadata, Column("id", String(36), primary_key=True),
    Column("password_hash", String(180), nullable=False))
sessions = Table("admin_sessions", metadata, Column("token_hash", String(64), primary_key=True),
    Column("admin_id", ForeignKey("local_admins.id", ondelete="CASCADE"), nullable=False),
    Column("expires_at", Integer, nullable=False))
# New authentication tables intentionally do not reuse pre-SSO administrator rows.
administrator_accounts = Table('regulation_administrator_accounts', metadata,
    Column('employee_no', String(6), primary_key=True), Column('password_hash', String(256), nullable=False),
    Column('failed_attempts', Integer, nullable=False), Column('locked_until', Integer, nullable=False),
    Column('credential_version', Integer, nullable=False), Column('must_change', Boolean, nullable=False))
# This export-only copy omits the private deployment's administrator identity.
administrator_sessions = Table('regulation_administrator_sessions', metadata,
    Column('token_hash', String(64), primary_key=True),
    Column('employee_no', ForeignKey('regulation_administrator_accounts.employee_no', ondelete='CASCADE'), nullable=False),
    Column('credential_version', Integer, nullable=False), Column('created_at', Integer, nullable=False),
    Column('last_seen_at', Integer, nullable=False), Column('expires_at', Integer, nullable=False))

audit = Table("admin_events", metadata, Column("id", String(36), primary_key=True),
    Column("actor", String(36), nullable=False), Column("action", String(40), nullable=False),
    Column("target_id", String(36), nullable=False), Column("created_at", String(40), nullable=False))


historical_records = Table("historical_records", metadata,
    Column("source_table", String(40), primary_key=True), Column("source_id", String(36), primary_key=True),
    Column("article_id", ForeignKey("regulatory_articles.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("payload", Text, nullable=False), Column("payload_sha256", String(64), nullable=False),
    UniqueConstraint("source_table", "article_id", name="uq_history_article_type"))
history_imports = Table("history_imports", metadata,
    Column("snapshot_id", String(64), primary_key=True), Column("source_system", String(100), nullable=False, unique=True),
    Column("imported_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("article_count", Integer, nullable=False), Column("record_count", Integer, nullable=False),
    Column("manifest", Text, nullable=False))
historical_files = Table("historical_files", metadata,
    Column("sha256", String(64), primary_key=True), Column("extension", String(8), nullable=False),
    Column("size", Integer, nullable=False), Column("content", LargeBinary, nullable=False))
historical_article_files = Table("historical_article_files", metadata,
    Column("article_id", ForeignKey("regulatory_articles.id", ondelete="CASCADE"), primary_key=True),
    Column("file_sha256", ForeignKey("historical_files.sha256"), primary_key=True, index=True),
    Column("source_url", Text, nullable=False))

article_metadata = Table("article_metadata", metadata,
    Column("article_id", ForeignKey("regulatory_articles.id", ondelete="CASCADE"), primary_key=True),
    Column("summary", Text, nullable=False), Column("importance_score", Integer, index=True),
    Column("created_at", String(40)), Column("display_title", String(1000), nullable=False))
article_display_dates = Table("article_display_dates", metadata,
    Column("article_id", ForeignKey("regulatory_articles.id", ondelete="CASCADE"), primary_key=True),
    Column("display_at", String(40)), Column("display_date_source", String(30)),
    CheckConstraint("display_date_source IN ('source', 'collected_fallback', 'legacy')",
                    name="ck_article_display_date_source"))
article_original_content = Table('article_original_content', metadata,
    Column('article_id', ForeignKey('regulatory_articles.id', ondelete='CASCADE'), primary_key=True),
    Column('source_version', String(128), nullable=False), Column('source_url', Text, nullable=False),
    Column('fetched_at', String(40), nullable=False), Column('tree', Text, nullable=False),
    Column('body_status', String(30), nullable=False), Column('unavailable_files', Text, nullable=False))
article_downloads = Table('article_downloads', metadata,
    Column('article_id', ForeignKey('regulatory_articles.id', ondelete='CASCADE'), primary_key=True),
    Column('file_sha256', ForeignKey('historical_files.sha256'), primary_key=True, index=True),
    Column('name', String(240), nullable=False), Column('kind', String(20), nullable=False),
    Column('ordinal', Integer, nullable=False), Column('source_url', Text, nullable=False),
    Column('fetched_at', String(40), nullable=False))
original_imports = Table('original_imports', metadata,
    Column('bundle_id', String(64), primary_key=True), Column('article_count', Integer, nullable=False),
    Column('file_count', Integer, nullable=False), Column('imported_at', String(40), nullable=False))
documents = Table("internal_documents", metadata,
    Column("id", String(36), primary_key=True), Column("title", String(120), nullable=False),
    Column("document_kind", String(20), nullable=False), Column("effective_date", String(10), nullable=False),
    Column("status", String(20), nullable=False, index=True), Column("revision", Integer, nullable=False),
    Column("sha256", String(64), unique=True), Column("content", LargeBinary, nullable=False),
    Column("warnings", Text, nullable=False), Column("warnings_acknowledged", Boolean, nullable=False),
    Column("error_code", String(60)), Column("created_at", String(40), nullable=False))
document_units = Table("internal_document_units", metadata,
    Column("document_id", ForeignKey("internal_documents.id", ondelete="CASCADE"), primary_key=True),
    Column("article_key", String(80), primary_key=True), Column("heading", String(500), nullable=False),
    Column("department", String(120), nullable=False), Column("body", Text, nullable=False),
    Column("start_paragraph", Integer, nullable=False), Column("end_paragraph", Integer, nullable=False),
    Column("reviewed", Boolean, nullable=False), Column("organization_names", Text, nullable=False))
duty_masters = Table("inspection_duty_masters", metadata,
    Column("id", String(36), primary_key=True), Column("version", String(80), nullable=False, unique=True),
    Column("fingerprint", String(64), nullable=False, unique=True), Column("payload", Text, nullable=False),
    Column("active", Boolean, nullable=False), Column("revision", Integer, nullable=False),
    Column("created_at", String(40), nullable=False))
inspections = Table("sanction_inspections", metadata,
    Column("id", String(36), primary_key=True), Column("article_id", ForeignKey("regulatory_articles.id"), nullable=False, index=True),
    Column("status", String(30), nullable=False), Column("is_historical", Boolean, nullable=False, server_default='false'), Column("result", Text), Column("review_draft", Text),
    Column("review_revision", Integer, nullable=False), Column("versions", Text, nullable=False),
    Column("automation_status", String(30), nullable=False), Column("error_code", String(80)),
    Column("created_at", String(40), nullable=False))
publications = Table("sanction_publications", metadata,
    Column("inspection_id", ForeignKey("sanction_inspections.id"), primary_key=True),
    Column("article_id", ForeignKey("regulatory_articles.id"), nullable=False, unique=True),
    Column("status", String(20), nullable=False), Column("report", Text, nullable=False),
    Column("published_at", String(40), nullable=False), Column("publication_source", String(20), nullable=False))
feature_receipts = Table("feature_migrations", metadata, Column("name", String(100), primary_key=True))
FEATURE_TABLES = (article_metadata, documents, document_units, duty_masters, inspections, publications, feature_receipts)


# Data-only imports retain their own receipts; never replace bootstrap snapshots.
transfer_sources = Table('data_transfer_sources', metadata,
    Column('article_id', ForeignKey('regulatory_articles.id'), primary_key=True),
    Column('source_hash', String(64), nullable=False), Column('payload', Text, nullable=False),
    Column('projection_hash', String(64), nullable=False))
transfer_batches = Table('data_transfer_batches', metadata,
    Column('id', String(64), primary_key=True), Column('status', String(24), nullable=False),
    Column('manifest', Text, nullable=False), Column('preview', Text), Column('receipt', Text),
    Column('error_code', String(60)), Column('created_at', String(40), nullable=False),
    Column('updated_at', String(40), nullable=False))
transfer_objects = Table('data_transfer_objects', metadata,
    Column('batch_id', ForeignKey('data_transfer_batches.id', ondelete='CASCADE'), primary_key=True),
    Column('sha256', String(64), primary_key=True), Column('kind', String(10), nullable=False),
    Column('size', Integer, nullable=False), Column('extension', String(8)),
    Column('verified', Boolean, nullable=False), Column('new_file', Boolean, nullable=False))
transfer_chunks = Table('data_transfer_chunks', metadata,
    Column('batch_id', ForeignKey('data_transfer_batches.id', ondelete='CASCADE'), primary_key=True),
    Column('sha256', String(64), primary_key=True), Column('part', Integer, primary_key=True),
    Column('chunk_sha256', String(64), nullable=False), Column('content', LargeBinary, nullable=False))


def now():
    return datetime.now(timezone.utc).isoformat()


def new_id():
    return str(uuid.uuid4())


def make_engine(url):
    options = {"pool_pre_ping": True}
    if str(url).startswith("sqlite"):
        options.update(connect_args={"check_same_thread": False, "timeout": 5})
        if str(url).endswith(":memory:"):
            options["poolclass"] = StaticPool
    else:
        options.update(pool_size=3, max_overflow=2, connect_args={"connect_timeout": 3,
                       "options": "-c statement_timeout=5000 -c lock_timeout=3000"})
    engine = create_engine(url, **options)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
    return engine


def migrate(engine, demo=False):
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            # One service replica; also serialize accidental concurrent migrations.
            from sqlalchemy import text
            conn.execute(text("SELECT pg_advisory_xact_lock(77461023)"))
        versions.create(conn, checkfirst=True)
        current = set(conn.execute(select(versions.c.version)).scalars())
        if current not in [set(range(1, n)) for n in range(1, 12)]:
            raise RuntimeError("Unsupported database schema version")
        if not current:
            metadata.create_all(conn, tables=[versions, posts, attachments, comments, limits, articles])
            conn.execute(insert(versions).values(version=1))
        if 2 not in current:
            for table in (admins, sessions, audit):
                table.create(conn, checkfirst=True)
            conn.execute(insert(versions).values(version=2))
        if 3 not in current:
            article_sources.create(conn, checkfirst=True)
            for index in article_list_indexes:
                index.create(conn, checkfirst=True)
            conn.execute(insert(versions).values(version=3))
        if 4 not in current:
            for table in (historical_records, history_imports, historical_files, historical_article_files):
                table.create(conn, checkfirst=True)
            if engine.dialect.name == "postgresql":
                # PostgreSQL DESC defaults to NULLS FIRST; match the explicit API order.
                for statement in (
                    "DROP INDEX IF EXISTS ix_articles_published_id",
                    "DROP INDEX IF EXISTS ix_articles_category_published_id",
                    "CREATE INDEX ix_articles_published_id ON regulatory_articles (published_at DESC NULLS LAST, id)",
                    "CREATE INDEX ix_articles_category_published_id ON regulatory_articles (category, published_at DESC NULLS LAST, id)",
                ):
                    conn.execute(text(statement))
            conn.execute(insert(versions).values(version=4))
        if 5 not in current:
            for table in FEATURE_TABLES:
                table.create(conn, checkfirst=True)
            conn.execute(insert(versions).values(version=5))
        if 6 not in current:
            from .agency_policy import exclude_from_database
            exclude_from_database(conn)
            conn.execute(insert(versions).values(version=6))
        if 7 not in current:
            article_display_dates.create(conn, checkfirst=True)
            conn.execute(insert(versions).values(version=7))
        if 8 not in current:
            for table in (article_original_content, article_downloads, original_imports):
                table.create(conn, checkfirst=True)
            if engine.dialect.name == 'postgresql':
                # Agency PDFs, HWPX/Office files and images are already compressed.
                # Keep TOAST out-of-line storage, avoiding redundant compression.
                conn.execute(text('ALTER TABLE historical_files ALTER COLUMN content SET STORAGE EXTERNAL'))
            conn.execute(insert(versions).values(version=8))
        if 9 not in current:
            for table in (administrator_accounts, administrator_sessions):
                table.create(conn, checkfirst=True)
            conn.execute(insert(versions).values(version=9))
        if 10 not in current:
            for table in (transfer_sources, transfer_batches, transfer_objects, transfer_chunks):
                table.create(conn, checkfirst=True)
            conn.execute(insert(versions).values(version=10))
        if demo and not conn.execute(select(articles.c.id).limit(1)).first():
            for category, title in [("press_release", "보도자료"), ("regulation_notice", "규제개정"), ("sanction_notice", "제재공시")]:
                conn.execute(insert(articles).values(id=new_id(), title=f"[개발 예시] {title} 조회 확인",
                    body="화면과 검색 동작을 확인하기 위한 가상 자료입니다. 실제 규제나 제재 내용이 아닙니다.",
                    category=category, agency=None, published_at=None, source_version="demo-v1", is_demo=True))
