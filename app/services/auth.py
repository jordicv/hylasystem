from flask import session

from app.services.supabase import get_public_client


def login_with_email_password(email, password):
    client = get_public_client()
    try:
        response = client.auth.sign_in_with_password({"email": email, "password": password})
        if not response.session:
            return {"error": "invalid"}
        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "user": response.user,
        }
    except Exception:
        return {"error": "invalid"}


def verify_access_token(token):
    client = get_public_client()
    try:
        user = client.auth.get_user(token)
        return user.user
    except Exception:
        return None


def logout_user():
    session.pop("access_token", None)
    session.pop("refresh_token", None)
