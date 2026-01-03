import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
from flask import Flask, g, redirect, render_template, request, session, url_for, flash, abort
from flask_wtf import CSRFProtect
from flask_wtf.csrf import generate_csrf
from markupsafe import Markup

from app.services.supabase import init_supabase
from app.services.auth import (
    login_with_email_password,
    verify_access_token,
    logout_user,
)
from app.services.rbac import (
    login_required,
    role_required,
    can_manage_user,
    can_access_lead,
    can_reassign_lead,
)
from app.services.users import (
    ensure_bootstrap_admin,
    get_user_profile,
    ensure_profile_for_auth_user,
    list_users,
    create_user,
    update_user,
)
from app.services.leads import (
    list_leads,
    create_lead,
    get_lead,
    update_lead,
    list_lead_images,
    upload_lead_image,
)
from app.services.audit import list_recent_audit_logs
from app.services.utils import (
    generate_wa_link,
    generate_wa_prefilled_link,
    generate_maps_link,
    is_valid_whatsapp,
    lead_statuses,
    demo_assignable_roles,
    user_roles,
    user_statuses,
)


def create_app():
    load_dotenv(override=True)
    app = Flask(__name__)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret")
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.jinja_env.auto_reload = True
    csrf = CSRFProtect()
    csrf.init_app(app)

    init_supabase()
    ensure_bootstrap_admin()

    @app.context_processor
    def inject_csrf():
        def csrf_input():
            token = generate_csrf()
            return Markup(f'<input type="hidden" name="csrf_token" value="{token}">')

        return {"csrf_input": csrf_input}

    @app.before_request
    def load_user():
        g.user = None
        token = session.get("access_token")
        if not token:
            return
        user = verify_access_token(token)
        if not user:
            logout_user()
            return
        profile = get_user_profile(user.id)
        if not profile:
            profile = ensure_profile_for_auth_user(user)
        if not profile:
            logout_user()
            return
        g.user = profile
        if g.user.get("status") in {"BLOQUEADO", "PAUSADO"}:
            logout_user()
            flash("Tu cuenta está bloqueada o pausada. Contacta al administrador.", "error")
            return redirect(url_for("login"))

    @app.before_request
    def block_pending_writes():
        if not g.get("user"):
            return
        if g.user.get("status") == "PENDIENTE" and request.method != "GET":
            if request.endpoint in {"logout"}:
                return
            flash("Cuenta pendiente de activación. No puedes realizar cambios.", "warning")
            return redirect(request.referrer or url_for("dashboard"))

    @app.route("/login", methods=["GET", "POST"])
    @csrf.exempt
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "").strip()
            if not email or not password:
                flash("Ingresa tu correo y contraseña.", "error")
                return render_template("login.html")
            result = login_with_email_password(email, password)
            if "error" in result:
                flash("Credenciales inválidas.", "error")
                return render_template("login.html")
            session["access_token"] = result["access_token"]
            session["refresh_token"] = result["refresh_token"]
            user = verify_access_token(result["access_token"])
            if not user:
                flash("No se pudo verificar el token.", "error")
                return render_template("login.html")
            profile = get_user_profile(user.id)
            if not profile:
                profile = ensure_profile_for_auth_user(user)
            if not profile:
                flash("No se encontró el perfil de usuario.", "error")
                return render_template("login.html")
            if profile.get("status") in {"BLOQUEADO", "PAUSADO"}:
                logout_user()
                flash("Tu cuenta está bloqueada o pausada. Contacta al administrador.", "error")
                return render_template("login.html")
            if profile.get("status") == "PENDIENTE":
                flash("Cuenta pendiente de activación.", "warning")
            return redirect(url_for("dashboard"))
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        logout_user()
        return redirect(url_for("login"))

    @app.route("/")
    @login_required
    def dashboard():
        leads = list_leads(g.user, status_filter=None)
        now = datetime.utcnow()
        pendientes = []
        for lead in leads:
            created_at = lead.get("created_at")
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00")).replace(tzinfo=None)
            if created_at and lead.get("status") == "NUEVO":
                if created_at < now - timedelta(days=3):
                    pendientes.append(lead)
            if lead.get("status") == "DEMO_REALIZADA":
                pendientes.append(lead)
        cards = {
            "activos": len([l for l in leads if l.get("status") not in {"NO_INTERESADO"}]),
            "demo_agendada": len([l for l in leads if l.get("status") == "DEMO_AGENDADA"]),
            "venta_cerrada": len([l for l in leads if l.get("status") == "VENTA_CERRADA"]),
        }
        return render_template("dashboard.html", cards=cards, pendientes=pendientes)

    @app.route("/admin/usuarios", methods=["GET", "POST"])
    @login_required
    @role_required(["ADMIN"])
    def admin_users():
        if request.method == "POST":
            form = request.form
            email = form.get("email", "").strip()
            password = form.get("password", "").strip()
            if "@" not in email:
                flash("Correo inválido.", "error")
                return redirect(url_for("admin_users"))
            if len(password) < 6:
                flash("La contraseña debe tener al menos 6 caracteres.", "error")
                return redirect(url_for("admin_users"))
            try:
                create_user(
                    actor=g.user,
                    email=email,
                    password=password,
                    name=form.get("name", "").strip(),
                    role=form.get("role"),
                    status=form.get("status"),
                    team_id=form.get("team_id"),
                    manager_user_id=form.get("manager_user_id") or None,
                    city=form.get("city", "").strip(),
                )
                flash("Usuario creado.", "success")
            except ValueError as exc:
                if str(exc) == "email_exists":
                    flash("Ya existe un usuario con ese correo.", "error")
                else:
                    flash("No se pudo crear el usuario.", "error")
            except Exception:
                flash("No se pudo crear el usuario.", "error")
            return redirect(url_for("admin_users"))
        users = list_users(actor=g.user)
        managers = [u for u in users if _role_name(u) == "JEFE"]
        return render_template(
            "admin_users.html",
            users=users,
            roles=user_roles(),
            statuses=user_statuses(),
            managers=managers,
        )

    @app.route("/admin/usuarios/<uid>/editar", methods=["GET", "POST"])
    @login_required
    @role_required(["ADMIN"])
    def admin_user_edit(uid):
        user = get_user_profile(uid)
        if not user:
            abort(404)
        if request.method == "POST":
            form = request.form
            update_user(
                actor=g.user,
                uid=uid,
                updates={
                    "name": form.get("name", "").strip(),
                    "city": form.get("city", "").strip(),
                    "role": form.get("role"),
                    "status": form.get("status"),
                    "team_id": form.get("team_id"),
                    "manager_user_id": form.get("manager_user_id") or None,
                },
            )
            flash("Usuario actualizado.", "success")
            return redirect(url_for("admin_users"))
        managers = [u for u in list_users(actor=g.user) if _role_name(u) == "JEFE"]
        return render_template(
            "user_edit.html",
            user=user,
            roles=user_roles(),
            statuses=user_statuses(),
            managers=managers,
        )

    @app.route("/jefe/usuarios", methods=["GET", "POST"])
    @login_required
    @role_required(["JEFE"])
    def jefe_users():
        if request.method == "POST":
            form = request.form
            email = form.get("email", "").strip()
            password = form.get("password", "").strip()
            if "@" not in email:
                flash("Correo inválido.", "error")
                return redirect(url_for("jefe_users"))
            if len(password) < 6:
                flash("La contraseña debe tener al menos 6 caracteres.", "error")
                return redirect(url_for("jefe_users"))
            try:
                create_user(
                    actor=g.user,
                    email=email,
                    password=password,
                    name=form.get("name", "").strip(),
                    role=form.get("role"),
                    status=form.get("status"),
                    team_id=g.user.get("team_id"),
                    manager_user_id=g.user.get("uid"),
                    city=form.get("city", "").strip(),
                )
                flash("Usuario creado.", "success")
            except ValueError as exc:
                if str(exc) == "email_exists":
                    flash("Ya existe un usuario con ese correo.", "error")
                else:
                    flash("No se pudo crear el usuario.", "error")
            except Exception:
                flash("No se pudo crear el usuario.", "error")
            return redirect(url_for("jefe_users"))
        users = list_users(actor=g.user)
        return render_template(
            "admin_users.html",
            users=users,
            roles=["VENDEDOR", "RECLUTA"],
            statuses=user_statuses(),
            jefe_scope=True,
        )

    @app.route("/jefe/usuarios/<uid>/editar", methods=["GET", "POST"])
    @login_required
    @role_required(["JEFE"])
    def jefe_user_edit(uid):
        user = get_user_profile(uid)
        if not user or not can_manage_user(g.user, user):
            abort(403)
        if request.method == "POST":
            form = request.form
            updates = {
                "name": form.get("name", "").strip(),
                "city": form.get("city", "").strip(),
                "status": form.get("status"),
            }
            update_user(actor=g.user, uid=uid, updates=updates)
            flash("Usuario actualizado.", "success")
            return redirect(url_for("jefe_users"))
        return render_template(
            "user_edit.html",
            user=user,
            roles=["VENDEDOR", "RECLUTA"],
            statuses=user_statuses(),
            jefe_scope=True,
        )

    @app.route("/leads")
    @login_required
    def leads_list():
        status = request.args.get("status")
        leads = list_leads(g.user, status_filter=status)
        users = []
        demo_users = []
        if g.user.get("role") in {"ADMIN", "JEFE"}:
            users = list_users(actor=g.user)
            demo_users = [u for u in users if _role_name(u) in demo_assignable_roles()]
        user_map = {u.get("uid"): u.get("name") for u in users}
        if not user_map:
            user_map = {g.user.get("uid"): g.user.get("name")}
        return render_template(
            "leads_list.html",
            leads=leads,
            statuses=lead_statuses(),
            user_map=user_map,
            demo_users=demo_users,
            can_assign_demo=g.user.get("role") in {"ADMIN", "JEFE"},
        )

    @app.route("/leads/nuevo", methods=["GET", "POST"])
    @login_required
    def lead_new():
        if request.method == "POST":
            form = request.form
            whatsapp = form.get("whatsapp_number", "").strip()
            if not is_valid_whatsapp(whatsapp):
                flash("WhatsApp inválido. Usa solo dígitos (9-15).", "error")
                return render_template(
                    "lead_new.html",
                    statuses=lead_statuses(),
                    demo_users=_get_demo_users(),
                )
            demo_user_id = form.get("demo_user_id") or None
            if not demo_user_id and g.user.get("role") in demo_assignable_roles():
                demo_user_id = g.user.get("uid")
            lead_id = create_lead(
                actor=g.user,
                data={
                    "first_name": form.get("first_name", "").strip(),
                    "last_name": form.get("last_name", "").strip(),
                    "occupation": form.get("occupation", "").strip(),
                    "whatsapp_number": whatsapp,
                    "address_line": form.get("address_line", "").strip(),
                    "city": form.get("city", "").strip(),
                    "region": form.get("region", "").strip(),
                    "country": form.get("country", "Chile").strip() or "Chile",
                    "status": form.get("status"),
                    "notes": form.get("notes", "").strip(),
                    "demo_user_id": demo_user_id,
                },
            )
            flash("Demo creada.", "success")
            return redirect(url_for("lead_detail", id=lead_id))
        demo_users = _get_demo_users()
        return render_template(
            "lead_new.html",
            statuses=lead_statuses(),
            demo_users=demo_users,
        )

    @app.route("/leads/<id>")
    @login_required
    def lead_detail(id):
        lead = get_lead(id)
        if not lead or not can_access_lead(g.user, lead):
            abort(403)
        seller_name = g.user.get("name", "")
        wa_link = generate_wa_link(lead.get("whatsapp_number"))
        message = (
            f"Hola {lead.get('first_name')}, soy {seller_name}. "
            "Te escribo por la demostración de HYLA. ¿Te acomoda coordinar un horario?"
        )
        wa_prefilled = generate_wa_prefilled_link(lead.get("whatsapp_number"), message)
        maps_link = generate_maps_link(
            lead.get("address_line"),
            lead.get("city"),
            lead.get("region"),
            lead.get("country"),
        )
        images = list_lead_images(id)
        logs = list_recent_audit_logs(entity_type="lead", entity_id=id)
        demo_users = _get_demo_users()
        demo_user_map = {u.get("uid"): u.get("name") for u in demo_users}
        if not demo_user_map:
            demo_user_map = {g.user.get("uid"): g.user.get("name")}
        return render_template(
            "lead_detail.html",
            lead=lead,
            wa_link=wa_link,
            wa_prefilled=wa_prefilled,
            maps_link=maps_link,
            images=images,
            logs=logs,
            demo_user_map=demo_user_map,
        )

    @app.route("/leads/<id>/editar", methods=["GET", "POST"])
    @login_required
    def lead_edit(id):
        lead = get_lead(id)
        if not lead or not can_access_lead(g.user, lead):
            abort(403)
        possible_owners = []
        if g.user.get("role") in {"ADMIN", "JEFE"}:
            possible_owners = list_users(actor=g.user)
        demo_users = _get_demo_users()
        if request.method == "POST":
            form = request.form
            whatsapp = form.get("whatsapp_number", "").strip()
            if not is_valid_whatsapp(whatsapp):
                flash("WhatsApp inválido. Usa solo dígitos (9-15).", "error")
                return render_template(
                    "lead_edit.html",
                    lead=lead,
                    statuses=lead_statuses(),
                    owners=possible_owners,
                )
            updates = {
                "first_name": form.get("first_name", "").strip(),
                "last_name": form.get("last_name", "").strip(),
                "occupation": form.get("occupation", "").strip(),
                "whatsapp_number": whatsapp,
                "address_line": form.get("address_line", "").strip(),
                "city": form.get("city", "").strip(),
                "region": form.get("region", "").strip(),
                "country": form.get("country", "Chile").strip() or "Chile",
                "status": form.get("status"),
                "notes": form.get("notes", "").strip(),
            }
            owner_user_id = form.get("owner_user_id")
            owner_ids = {u.get("uid") for u in possible_owners}
            if owner_user_id and owner_user_id in owner_ids and can_reassign_lead(g.user, lead, owner_user_id):
                updates["owner_user_id"] = owner_user_id
            demo_user_id = form.get("demo_user_id")
            demo_ids = {u.get("uid") for u in demo_users}
            if demo_user_id and demo_user_id in demo_ids:
                updates["demo_user_id"] = demo_user_id
            update_lead(actor=g.user, lead_id=id, updates=updates)
            flash("Demo actualizada.", "success")
            return redirect(url_for("lead_detail", id=id))
        return render_template(
            "lead_edit.html",
            lead=lead,
            statuses=lead_statuses(),
            owners=possible_owners,
            demo_users=demo_users,
        )

    @app.route("/leads/<id>/subir-imagen", methods=["POST"])
    @login_required
    def lead_upload_image(id):
        lead = get_lead(id)
        if not lead or not can_access_lead(g.user, lead):
            abort(403)
        file = request.files.get("image")
        if not file:
            flash("Selecciona una imagen.", "error")
            return redirect(url_for("lead_detail", id=id))
        result = upload_lead_image(actor=g.user, lead_id=id, file=file)
        if "error" in result:
            flash(result["error"], "error")
        else:
            flash("Imagen subida.", "success")
        return redirect(url_for("lead_detail", id=id))

    @app.route("/leads/<id>/estado", methods=["POST"])
    @login_required
    def lead_quick_status(id):
        lead = get_lead(id)
        if not lead or not can_access_lead(g.user, lead):
            abort(403)
        status = request.form.get("status")
        if status not in lead_statuses():
            flash("Estado inválido.", "error")
            return redirect(url_for("leads_list"))
        update_lead(actor=g.user, lead_id=id, updates={"status": status})
        flash("Estado actualizado.", "success")
        return redirect(url_for("leads_list"))

    def _get_demo_users():
        if g.user.get("role") in {"ADMIN", "JEFE"}:
            users = list_users(actor=g.user)
            return [u for u in users if _role_name(u) in demo_assignable_roles()]
        return []

    def _role_name(user):
        return (user.get("role") or "").strip().upper()

    @app.route("/leads/<id>/demo-asignada", methods=["POST"])
    @login_required
    def lead_quick_demo_assign(id):
        lead = get_lead(id)
        if not lead or not can_access_lead(g.user, lead):
            abort(403)
        demo_users = _get_demo_users()
        demo_ids = {u.get("uid") for u in demo_users}
        demo_user_id = request.form.get("demo_user_id")
        if demo_user_id and demo_user_id not in demo_ids:
            flash("Usuario inválido.", "error")
            return redirect(url_for("leads_list"))
        update_lead(actor=g.user, lead_id=id, updates={"demo_user_id": demo_user_id or None})
        flash("Demo asignada actualizada.", "success")
        return redirect(url_for("leads_list"))

    return app


app = create_app()
