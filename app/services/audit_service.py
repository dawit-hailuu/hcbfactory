"""
Centralized audit log. Every destructive or money-related action calls
audit_service.log() so admins can later see who did what.
"""
from app.database.db import get_connection
from app.utils import clock


def log(user_id: int, action: str, details: str = None):
    """Record an audit entry. Never raises — audit failure must not block business."""
    try:
        conn = get_connection()
        try:
            conn.execute(
                """INSERT INTO audit_log (user_id, action, details, created_at)
                   VALUES (?,?,?,?)""",
                (user_id, action, details, clock.now()),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def list_entries(limit: int = 500, date_from: str = None, date_to: str = None):
    conn = get_connection()
    try:
        where, params = [], []
        if date_from:
            where.append("a.created_at >= ?"); params.append(date_from + " 00:00:00")
        if date_to:
            where.append("a.created_at <= ?"); params.append(date_to + " 23:59:59")
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        params.append(limit)
        rows = conn.execute(
            f"""SELECT a.id, a.created_at, a.action, a.details,
                       COALESCE(u.username, '(system)') AS username
                  FROM audit_log a
             LEFT JOIN users u ON u.id = a.user_id
                {clause}
              ORDER BY a.id DESC LIMIT ?""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
