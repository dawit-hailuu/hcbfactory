"""
Centralized audit log. Every notable action calls audit_service.log()
so owners/managers can see who did what.
Uses the core AuditLog ORM class.
"""
from datetime import datetime
from app.database.db import get_session, get_connection
from app.database.models import AuditLog, User

def log(user_id: int, action: str, details: str = None):
    """Record an audit entry. Never raises — audit failure must not block business."""
    session = get_session()
    try:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            details=details,
            created_at=datetime.now()
        )
        session.add(entry)
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()

def list_entries(limit: int = 500, date_from: str = None, date_to: str = None):
    conn = get_connection()
    try:
        where = []
        params = []
        if date_from:
            where.append("a.created_at >= ?")
            params.append(date_from + " 00:00:00")
        if date_to:
            where.append("a.created_at <= ?")
            params.append(date_to + " 23:59:59")
            
        clause = "WHERE " + " AND ".join(where) if where else ""
        sql = f"""
            SELECT a.id, datetime(a.created_at) AS created_at, a.action, a.details,
                   COALESCE(u.username, '(system)') AS username
            FROM audit_log a
            LEFT JOIN users u ON u.id = a.user_id
            {clause}
            ORDER BY a.id DESC
            LIMIT ?
        """
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
