"""Preserved admin business operations; HTTP authorization uses a separate administrator session."""
from sqlalchemy import select, insert, func
from .database import audit, posts, comments, now, new_id
from .security import Problem
from .audit_log import pending


def record_event(conn, actor, action, target_id):
    conn.execute(insert(audit).values(id=new_id(), actor=actor, action=action,
                                    target_id=target_id, created_at=now()))
    pending(conn, action, actor, target_id)


def overview(engine, settings, actor_id, page):
    if not actor_id:
        raise Problem("unauthorized", 401)
    with engine.connect() as conn:
        counts = {status: conn.execute(select(func.count()).select_from(posts).where(posts.c.status == status)).scalar_one()
                  for status in ("published", "draft")}
        counts["comments"] = conn.execute(select(func.count()).select_from(comments)).scalar_one()
        total = conn.execute(select(func.count()).select_from(audit)).scalar_one()
        events = [dict(row) for row in conn.execute(select(audit).order_by(audit.c.created_at.desc(), audit.c.id).limit(20).offset((page - 1) * 20)).mappings()]
    return {"counts": counts, "events": events, "total": total, "page": page,
            "source": settings.source_mode, "geni": settings.geni_mode, "environment": settings.environment}
