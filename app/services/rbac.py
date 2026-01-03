from functools import wraps

from flask import g, redirect, url_for, flash, abort


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.get("user"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def role_required(roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not g.get("user"):
                return redirect(url_for("login"))
            if g.user.get("role") not in roles:
                flash("No tienes permisos para acceder.", "error")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)

        return wrapped

    return decorator


def can_manage_user(actor, target):
    if actor.get("role") == "ADMIN":
        return True
    if actor.get("role") == "JEFE":
        return target.get("team_id") == actor.get("team_id")
    return False


def can_access_lead(actor, lead):
    role = actor.get("role")
    if role == "ADMIN":
        return True
    if role == "JEFE":
        return lead.get("team_id") == actor.get("team_id")
    return lead.get("owner_user_id") == actor.get("uid")


def can_reassign_lead(actor, lead, new_owner_id):
    if actor.get("role") == "ADMIN":
        return True
    if actor.get("role") == "JEFE" and lead.get("team_id") == actor.get("team_id"):
        return True
    return False
