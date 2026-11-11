"""Bounded, secret-free audit file in the platform's persistent logs directory."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from sqlalchemy import event

PATH = Path('/logs/admin-audit.log')
logger = logging.getLogger('vibelabs.admin_audit')
logger.setLevel(logging.INFO)


def attach(engine, production=False):
    handler = None
    if production:
        PATH.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(PATH, maxBytes=5*1024*1024, backupCount=4, encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        logger.addHandler(handler)

    def committed(conn):
        # SQLAlchemy fires this immediately before DBAPI commit. DB admin_events
        # remains the authoritative record if that commit subsequently fails.
        for action, actor, target in conn.info.pop('admin_audit_pending', []):
            logger.info('transaction_commit_requested action=%s account=%s target=%s', action, actor, target)

    def rolled_back(conn):
        conn.info.pop('admin_audit_pending', None)

    event.listen(engine, 'commit', committed)
    event.listen(engine, 'rollback', rolled_back)

    def close():
        event.remove(engine, 'commit', committed)
        event.remove(engine, 'rollback', rolled_back)
        if handler:
            logger.removeHandler(handler)
            handler.close()
    return close


def pending(conn, action, actor, target):
    # All callers use fixed action names and server IDs; no request payloads.
    conn.info.setdefault('admin_audit_pending', []).append((action, actor, target))
