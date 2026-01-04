import os
import uuid
from datetime import datetime

from app.services.supabase import get_admin_client
from app.services.audit import log_event
from app.services.utils import allowed_image_extension


def list_leads(actor, status_filter=None):
    admin = get_admin_client()
    query = admin.table("leads").select("*").order("created_at", desc=True)
    role = actor.get("role")
    if role == "JEFE":
        query = query.eq("team_id", actor.get("team_id"))
    elif role in {"VENDEDOR", "RECLUTA"}:
        query = query.eq("owner_user_id", actor.get("uid"))
    if status_filter:
        query = query.eq("status", status_filter)
    result = query.execute()
    return [dict(row) for row in result.data]


def create_lead(actor, data):
    admin = get_admin_client()
    now = datetime.utcnow().isoformat()
    lead_data = {
        **data,
        "owner_user_id": actor.get("uid"),
        "team_id": actor.get("team_id"),
        "created_at": now,
        "updated_at": now,
    }
    result = admin.table("leads").insert(lead_data).execute()
    lead_id = result.data[0]["id"]
    log_event(
        actor=actor,
        action="CREATE",
        entity_type="lead",
        entity_id=lead_id,
        team_id=actor.get("team_id"),
        before=None,
        after=lead_data,
    )
    return lead_id


def get_lead(lead_id):
    admin = get_admin_client()
    result = admin.table("leads").select("*").eq("id", lead_id).limit(1).execute()
    if not result.data:
        return None
    return dict(result.data[0])


def update_lead(actor, lead_id, updates):
    admin = get_admin_client()
    before = get_lead(lead_id)
    updates["updated_at"] = datetime.utcnow().isoformat()
    admin.table("leads").update(updates).eq("id", lead_id).execute()
    after = get_lead(lead_id)
    action = "UPDATE"
    if "status" in updates:
        action = "STATUS_CHANGE"
    if "owner_user_id" in updates:
        action = "ASSIGN"
    log_event(
        actor=actor,
        action=action,
        entity_type="lead",
        entity_id=lead_id,
        team_id=after.get("team_id"),
        before=before,
        after=after,
    )
    return after


def list_lead_images(lead_id):
    admin = get_admin_client()
    result = (
        admin.table("lead_images")
        .select("*")
        .eq("lead_id", lead_id)
        .order("uploaded_at", desc=True)
        .execute()
    )
    bucket = os.environ.get("SUPABASE_STORAGE_BUCKET", "lead-images")
    images = []
    for row in result.data:
        item = dict(row)
        storage_path = item.get("storage_path")
        if storage_path:
            signed = admin.storage.from_(bucket).create_signed_url(storage_path, 60 * 60 * 6)
            url = signed.get("signedURL") or signed.get("signedUrl") or item.get("url") or ""
            item["url"] = url
        images.append(item)
    return images


def upload_lead_image(actor, lead_id, file):
    filename = file.filename or ""
    if not allowed_image_extension(filename):
        return {"error": "Formato no permitido. Usa jpg, jpeg, png o webp."}
    file.seek(0, os.SEEK_END)
    size = file.tell()
    if size > 5 * 1024 * 1024:
        return {"error": "La imagen supera los 5MB."}
    file.seek(0)
    ext = filename.rsplit(".", 1)[-1].lower()
    image_id = str(uuid.uuid4())
    storage_path = f"leads/{lead_id}/{image_id}.{ext}"
    admin = get_admin_client()
    bucket = os.environ.get("SUPABASE_STORAGE_BUCKET", "lead-images")
    file_bytes = file.read()
    admin.storage.from_(bucket).upload(storage_path, file_bytes, file_options={"content-type": file.content_type})
    signed = admin.storage.from_(bucket).create_signed_url(storage_path, 60 * 60 * 6)
    url = signed.get("signedURL") or signed.get("signedUrl") or ""
    data = {
        "id": image_id,
        "lead_id": lead_id,
        "storage_path": storage_path,
        "url": url,
        "uploaded_by": actor.get("uid"),
        "uploaded_at": datetime.utcnow().isoformat(),
    }
    admin.table("lead_images").insert(data).execute()
    log_event(
        actor=actor,
        action="IMAGE_UPLOAD",
        entity_type="image",
        entity_id=image_id,
        team_id=actor.get("team_id"),
        before=None,
        after=data,
    )
    return {"id": image_id, **data}
