"""Agency scope for the bank deployment, including durable exclusion on upgrade."""
from sqlalchemy import column, delete, func, literal_column, or_, select, text, update, inspect

EXCLUDED_AGENCY = 'MAFRA'
# Match Python's whitespace trimming explicitly in both database dialects.
AGENCY_WHITESPACE = ''.join(chr(code) for code in range(0x3001) if chr(code).isspace())


def is_excluded(agency):
    return isinstance(agency, str) and agency.strip(AGENCY_WHITESPACE).upper() == EXCLUDED_AGENCY


def normalized_agency(value, dialect):
    trim = func.btrim if dialect == 'postgresql' else func.trim
    return func.upper(trim(value, AGENCY_WHITESPACE))


def exclude_from_database(conn):
    """Called once by v6, inside the schema migration's transaction and lock."""
    from .database import (articles, article_sources, historical_records, history_imports,
                           historical_files, historical_article_files, inspections, publications, article_downloads)
    ids = select(articles.c.id).where(normalized_agency(articles.c.agency, conn.dialect.name) == EXCLUDED_AGENCY)
    inspection_ids = select(inspections.c.id).where(inspections.c.article_id.in_(ids))
    file_ids = list(conn.execute(select(historical_article_files.c.file_sha256)
        .where(historical_article_files.c.article_id.in_(ids)).distinct()).scalars())
    has_downloads = inspect(conn).has_table(article_downloads.name)
    if has_downloads:
        file_ids.extend(conn.execute(select(article_downloads.c.file_sha256).where(article_downloads.c.article_id.in_(ids))).scalars())
    source_systems = list(conn.execute(select(article_sources.c.source_system)
        .where(article_sources.c.article_id.in_(ids)).distinct()).scalars())
    # These two feature tables deliberately do not cascade on article deletion.
    conn.execute(delete(publications).where(or_(publications.c.article_id.in_(ids),
                                                publications.c.inspection_id.in_(inspection_ids))))
    conn.execute(delete(inspections).where(inspections.c.article_id.in_(ids)))
    # Raw records, summaries, source identity and article-file links cascade.
    conn.execute(delete(articles).where(articles.c.id.in_(ids)))
    if file_ids:
        statement = delete(historical_files).where(historical_files.c.sha256.in_(file_ids),
            ~historical_files.c.sha256.in_(select(historical_article_files.c.file_sha256)))
        if has_downloads:statement = statement.where(~historical_files.c.sha256.in_(select(article_downloads.c.file_sha256)))
        conn.execute(statement)
    for source in source_systems:
        remaining = select(article_sources.c.article_id).where(article_sources.c.source_system == source)
        count = conn.execute(select(func.count()).select_from(article_sources)
            .where(article_sources.c.source_system == source)).scalar_one()
        records = conn.execute(select(func.count()).select_from(historical_records)
            .where(historical_records.c.article_id.in_(remaining))).scalar_one()
        conn.execute(update(history_imports).where(history_imports.c.source_system == source)
            .values(article_count=count, record_count=records))

    if conn.dialect.name == 'postgresql':
        predicate = normalized_agency(column('agency'), conn.dialect.name) != EXCLUDED_AGENCY
        condition = str(predicate.compile(dialect=conn.dialect, compile_kwargs={'literal_binds': True}))
        conn.execute(text("ALTER TABLE regulatory_articles ADD CONSTRAINT ck_articles_exclude_mafra "
                          f"CHECK ({condition})"))
    else:
        # SQLite cannot add a CHECK to an existing table without rebuilding it.
        predicate = normalized_agency(literal_column('NEW.agency'), conn.dialect.name) == EXCLUDED_AGENCY
        condition = str(predicate.compile(dialect=conn.dialect, compile_kwargs={'literal_binds': True}))
        for action in ('INSERT', 'UPDATE OF agency'):
            suffix = 'insert' if action == 'INSERT' else 'update'
            conn.execute(text(f"CREATE TRIGGER IF NOT EXISTS articles_exclude_mafra_{suffix} "
                f"BEFORE {action} ON regulatory_articles "
                f"WHEN {condition} "
                "BEGIN SELECT RAISE(ABORT, 'excluded agency'); END"))
