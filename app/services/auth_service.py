"""
Authentication and User Access Control (UAC) service.
Verifies credentials, manages users, and handles action-level permissions and templates.
"""
import hashlib
from app.database.db import get_session, get_connection
from app.database.models import User, Permission, UserPermission

# Default Action Permission Presets
ROLE_PRESETS = {
    "cashier": ["sale:create"],
    "manager": [
        "sale:create", "inventory:add-stock", "inventory:adjust", 
        "inventory:disposal", "production:create", "audit:view"
    ],
    "owner": [
        "sale:create", "sale:void", "inventory:add-stock", "inventory:adjust", 
        "inventory:disposal", "production:create", "system:update-price", 
        "user:manage", "audit:view"
    ]
}


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


def authenticate(username: str, password: str):
    """Verifies credentials and returns a user dictionary, or None."""
    session = get_session()
    try:
        u = session.query(User).filter_by(
            username=username,
            password_hash=_hash(password)
        ).first()
        if u:
            return {
                "id": u.id,
                "username": u.username,
                "full_name": u.full_name,
                "role": u.role,
                "created_at": u.created_at.strftime("%Y-%m-%d %H:%M:%S")
            }
        return None
    finally:
        session.close()


def list_users():
    session = get_session()
    try:
        users = session.query(User).order_by(User.username).all()
        return [
            {
                "id": u.id,
                "username": u.username,
                "full_name": u.full_name,
                "role": u.role,
                "created_at": u.created_at.strftime("%Y-%m-%d %H:%M:%S")
            } for u in users
        ]
    finally:
        session.close()


def create_user(username: str, password: str, full_name: str, role: str):
    """Creates a new user and automatically seeds their permission presets."""
    if role not in ("owner", "manager", "cashier"):
        raise ValueError("role must be 'owner', 'manager', or 'cashier'")
        
    session = get_session()
    try:
        existing = session.query(User).filter_by(username=username).first()
        if existing:
            raise ValueError(f"Username '{username}' is already taken.")
            
        u = User(
            username=username,
            password_hash=_hash(password),
            full_name=full_name,
            role=role
        )
        session.add(u)
        session.flush()
        
        # Apply role-based default presets
        reset_user_permissions(u.id, role, session=session)
        
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def change_password(user_id: int, new_password: str):
    session = get_session()
    try:
        u = session.query(User).filter_by(id=user_id).first()
        if u:
            u.password_hash = _hash(new_password)
            session.commit()
    finally:
        session.close()


def delete_user(user_id: int):
    session = get_session()
    try:
        u = session.query(User).filter_by(id=user_id).first()
        if u:
            session.delete(u)
            session.commit()
    finally:
        session.close()


def has_permission(user_id: int, action_key: str) -> bool:
    """
    Checks if a user is allowed to perform a specific action.
    Owners always have full permission.
    """
    session = get_session()
    try:
        u = session.query(User).filter_by(id=user_id).first()
        if not u:
            return False
            
        if u.role == "owner":
            return True
            
        # Check permissions join
        perm = session.query(UserPermission).join(Permission).filter(
            UserPermission.user_id == user_id,
            Permission.action_key == action_key,
            UserPermission.is_allowed == True
        ).first()
        
        return perm is not None
    finally:
        session.close()


def get_user_permissions(user_id: int):
    """Returns a dictionary of action keys mapping to whether the user is allowed."""
    session = get_session()
    try:
        all_perms = session.query(Permission).all()
        user_up = session.query(UserPermission).filter_by(user_id=user_id).all()
        allowed_keys = {up.permission.action_key for up in user_up if up.is_allowed}
        
        # If user is owner, they have everything
        u = session.query(User).filter_by(id=user_id).first()
        is_owner = u and u.role == "owner"
        
        return {
            p.action_key: (True if is_owner else (p.action_key in allowed_keys))
            for p in all_perms
        }
    finally:
        session.close()


def grant_permission(user_id: int, action_key: str, session=None):
    """Enforces specific action approval for a user."""
    own_session = session is None
    if own_session:
        session = get_session()
        
    try:
        perm = session.query(Permission).filter_by(action_key=action_key).first()
        if not perm:
            raise ValueError(f"Permission action '{action_key}' does not exist.")
            
        up = session.query(UserPermission).filter_by(user_id=user_id, permission_id=perm.id).first()
        if up:
            up.is_allowed = True
        else:
            up = UserPermission(user_id=user_id, permission_id=perm.id, is_allowed=True)
            session.add(up)
            
        if own_session:
            session.commit()
    except Exception as e:
        if own_session:
            session.rollback()
        raise e
    finally:
        if own_session:
            session.close()


def revoke_permission(user_id: int, action_key: str, session=None):
    """Explicitly blocks an action key for a user."""
    own_session = session is None
    if own_session:
        session = get_session()
        
    try:
        perm = session.query(Permission).filter_by(action_key=action_key).first()
        if not perm:
            return
            
        up = session.query(UserPermission).filter_by(user_id=user_id, permission_id=perm.id).first()
        if up:
            up.is_allowed = False
            
        if own_session:
            session.commit()
    except Exception as e:
        if own_session:
            session.rollback()
        raise e
    finally:
        if own_session:
            session.close()


def reset_user_permissions(user_id: int, role: str, session=None):
    """Clears any user custom configurations and applies default preset limits."""
    own_session = session is None
    if own_session:
        session = get_session()
        
    try:
        # Delete existing permissions
        session.query(UserPermission).filter_by(user_id=user_id).delete()
        session.flush()
        
        # Apply new preset list
        actions = ROLE_PRESETS.get(role, [])
        for act in actions:
            perm = session.query(Permission).filter_by(action_key=act).first()
            if perm:
                up = UserPermission(user_id=user_id, permission_id=perm.id, is_allowed=True)
                session.add(up)
                
        if own_session:
            session.commit()
    except Exception as e:
        if own_session:
            session.rollback()
        raise e
    finally:
        if own_session:
            session.close()
