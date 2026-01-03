from datetime import datetime

from app.services.supabase import get_admin_client


def log_event(
    actor,
    action,
    entity_type,
    entity_id,
    team_id,
    before=None,
    after=None,
):
    admin = get_admin_client()
    data = {
        "timestamp": datetime.utcnow().isoformat(),
        "actor_user_id": actor.get("uid"),
        "actor_name": actor.get("name"),
        "action": action,
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "team_id": team_id,
        "before": before or {},
        "after": after or {},
    }
    admin.table("audit_logs").insert(data).execute()


def list_recent_audit_logs(entity_type, entity_id, limit=20):
    admin = get_admin_client()
    result = (
        admin.table("audit_logs")
        .select("*")
        .eq("entity_type", entity_type)
        .eq("entity_id", str(entity_id))
        .order("timestamp", desc=True)
        .limit(limit)
        .execute()
    )
    return [dict(row) for row in result.data]
