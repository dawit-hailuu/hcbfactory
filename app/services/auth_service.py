"""Authentication service. Verifies credentials and manages users."""
import hashlib
from app.database.db import get_connection


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


def authenticate(username: str, password: str):
    """Return user row dict if credentials valid, else None."""
    from app.services import audit_service
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ? AND password_hash = ?",
            (username, _hash(password)),
        ).fetchone()
        if row:
            d = dict(row)
            audit_service.log(d["id"], "login_success", f"user={username}")
            return d
        # Failed login: no user_id known yet
        audit_service.log(None, "login_failure", f"attempted_username={username}")
        return None
    finally:
        conn.close()


def list_users():
    conn = get_connection()
    try:
        return [dict(r) for r in conn.execute(
            "SELECT id, username, full_name, role, created_at FROM users ORDER BY username"
        ).fetchall()]
    finally:
        conn.close()


def create_user(username: str, password: str, full_name: str, role: str):
    if role not in ("admin", "worker"):
        raise ValueError("role must be 'admin' or 'worker'")
    from app.services import audit_service
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, full_name, role) VALUES (?,?,?,?)",
            (username, _hash(password), full_name, role),
        )
        conn.commit()
        audit_service.log(None, "user_create", f"username={username} role={role}")
    finally:
        conn.close()


def change_password(user_id: int, new_password: str):
    from app.services import audit_service
    conn = get_connection()
    try:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                     (_hash(new_password), user_id))
        conn.commit()
        audit_service.log(user_id, "password_change", f"user_id={user_id}")
    finally:
        conn.close()


def delete_user(user_id: int):
    from app.services import audit_service
    conn = get_connection()
    try:
        row = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        if row:
            audit_service.log(None, "user_delete", f"username={row['username']}")
    finally:
        conn.close()
