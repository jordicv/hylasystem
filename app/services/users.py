from datetime import datetime

from app.services.supabase import get_admin_client
from app.services.audit import log_event


def ensure_bootstrap_admin():
    email = _env("BOOTSTRAP_ADMIN_EMAIL")
    password = _env("BOOTSTRAP_ADMIN_PASSWORD")
    name = _env("BOOTSTRAP_ADMIN_NAME")
    city = _env("BOOTSTRAP_ADMIN_CITY", "")
    if not email or not password or not name:
        return
    admin = get_admin_client()
    try:
        user = _get_user_by_email(admin, email)
        if not user:
            user = admin.auth.admin.create_user(
                {
                    "email": email,
                    "password": password,
                    "email_confirm": True,
                }
            ).user
    except Exception:
        return
    uid = user.id
    if _profile_exists(admin, uid):
        return
    now = datetime.utcnow().isoformat()
    data = {
        "id": uid,
        "name": name,
        "email": email,
        "role": "ADMIN",
        "status": "ACTIVO",
        "city": city,
        "team_id": "default",
        "manager_user_id": None,
        "created_at": now,
        "updated_at": now,
    }
    admin.table("users").insert(data).execute()


def list_users(actor):
    admin = get_admin_client()
    query = admin.table("users").select("*")
    if actor.get("role") == "JEFE":
        query = query.eq("team_id", actor.get("team_id"))
    result = query.execute()
    return [_normalize_user(row) for row in result.data]


def get_user_profile(uid):
    admin = get_admin_client()
    result = admin.table("users").select("*").eq("id", uid).limit(1).execute()
    if not result.data:
        return None
    return _normalize_user(result.data[0])


def ensure_profile_for_auth_user(user):
    admin = get_admin_client()
    if not user or not user.id:
        return None
    if _profile_exists(admin, user.id):
        return get_user_profile(user.id)
    data = {
        "id": user.id,
        "name": user.user_metadata.get("name") if user.user_metadata else user.email,
        "email": user.email,
        "role": "RECLUTA",
        "status": "PENDIENTE",
        "city": "",
        "team_id": "default",
        "manager_user_id": None,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    try:
        admin.table("users").insert(data).execute()
        return _normalize_user(data)
    except Exception:
        return None


def create_user(
    actor,
    email,
    password,
    name,
    role,
    status,
    team_id,
    manager_user_id,
    city,
):
    admin = get_admin_client()
    if actor.get("role") == "JEFE":
        role = role if role in {"VENDEDOR", "RECLUTA"} else "RECLUTA"
        team_id = actor.get("team_id")
        manager_user_id = actor.get("uid")
    if manager_user_id and not _valid_uuid(manager_user_id):
        manager_user_id = None
    existing_user = _get_user_by_email(admin, email)
    if existing_user:
        uid = existing_user.id
        if _profile_exists(admin, uid):
            raise ValueError("email_exists")
    else:
        try:
            user = admin.auth.admin.create_user(
                {"email": email, "password": password, "email_confirm": True}
            ).user
            uid = user.id
        except Exception as exc:
            if "already been registered" in str(exc):
                existing_user = _get_user_by_email(admin, email)
                if existing_user:
                    uid = existing_user.id
                    if _profile_exists(admin, uid):
                        raise ValueError("email_exists") from exc
                else:
                    raise
            else:
                raise
    now = datetime.utcnow().isoformat()
    data = {
        "id": uid,
        "name": name,
        "email": email,
        "role": role,
        "status": status,
        "city": city,
        "team_id": team_id,
        "manager_user_id": manager_user_id,
        "created_at": now,
        "updated_at": now,
    }
    admin.table("users").insert(data).execute()
    log_event(
        actor=actor,
        action="CREATE",
        entity_type="user",
        entity_id=uid,
        team_id=team_id,
        before=None,
        after=data,
    )
    return uid


def update_user(actor, uid, updates):
    admin = get_admin_client()
    if "manager_user_id" in updates and updates["manager_user_id"] and not _valid_uuid(updates["manager_user_id"]):
        updates["manager_user_id"] = None
    before = get_user_profile(uid)
    updates["updated_at"] = datetime.utcnow().isoformat()
    admin.table("users").update(updates).eq("id", uid).execute()
    after = get_user_profile(uid)
    action = "USER_STATUS_CHANGE" if "status" in updates else "UPDATE"
    log_event(
        actor=actor,
        action=action,
        entity_type="user",
        entity_id=uid,
        team_id=after.get("team_id"),
        before=before,
        after=after,
    )
    return after


def _profile_exists(admin, uid):
    result = admin.table("users").select("id").eq("id", uid).limit(1).execute()
    return bool(result.data)


def _get_user_by_email(admin, email):
    try:
        return admin.auth.admin.get_user_by_email(email).user
    except Exception:
        return None


def _normalize_user(row):
    row = dict(row)
    row["uid"] = row.get("id")
    return row


def _valid_uuid(value):
    import uuid

    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


def _env(key, default=None):
    import os

    return os.environ.get(key, default)
