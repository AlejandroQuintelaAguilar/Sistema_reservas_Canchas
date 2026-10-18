import re
import secrets
from datetime import date, datetime, timedelta

from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy.exc import IntegrityError

from extensions import db
from models.administrador import Administrador
from models.cliente import Cliente
from models.empleado import Empleado
from models.persona import Persona
from models.usuario import Usuario
from services.auth_service import (
    BLOQUEO_MINUTOS,
    MAX_INTENTOS_LOGIN,
    _extract_bearer_token,
    create_reset_token,
    create_token,
    decode_token,
    frontend_role,
    hash_password,
    limpiar_tokens_expirados,
    require_auth,
    revocar_token,
    verify_password,
)
from services.email_service import send_recovery_email, smtp_is_configured
from validators.auth_validator import validar_password

auth_bp = Blueprint("auth", __name__)
admin_bp = Blueprint("admin", __name__)

VALID_ROLES = ("cliente", "administrador", "empleado")
FRONTEND_TO_DB_ROLE = {
    "admin": "administrador",
    "user": "cliente",
    "empleado": "empleado",
    "administrador": "administrador",
    "cliente": "cliente",
}


def _json():
    return request.get_json(silent=True) or {}


def _split_nombre(nombre_completo, apellido_explicit=None):
    parts = (nombre_completo or "").strip().split()
    nombre = parts[0] if parts else ""
    if apellido_explicit and str(apellido_explicit).strip():
        apellido = str(apellido_explicit).strip()
    else:
        apellido = " ".join(parts[1:]) if len(parts) > 1 else nombre
    return nombre[:80], apellido[:80]


def _unique_username(base):
    cleaned = re.sub(r"[^a-zA-Z0-9._]", "", (base or "").strip())[:40] or "usuario"
    candidate = cleaned
    n = 1
    while Usuario.query.filter_by(username=candidate).first():
        suffix = str(n)
        candidate = f"{cleaned[: 50 - len(suffix)]}{suffix}"
        n += 1
    return candidate


def _unique_ci(preferred=None):
    if preferred:
        existing = Persona.query.filter_by(ci=preferred).first()
        if not existing:
            return preferred[:20]
    for _ in range(20):
        ci = secrets.token_hex(8)[:20]
        if not Persona.query.filter_by(ci=ci).first():
            return ci
    raise RuntimeError("No se pudo generar un CI único")


def _serialize_user(user):
    persona = user.persona
    nombre_completo = (
        f"{persona.nombre} {persona.apellido}" if persona else user.username
    )

    # Obtener IDs de las tablas especializadas
    id_cliente = None
    id_administrador = None
    id_empleado = None

    if user.rol == "cliente":
        cliente = Cliente.query.filter_by(id_usuario=user.id_usuario).first()
        if cliente:
            id_cliente = cliente.id_cliente
    elif user.rol in ("administrador", "admin"):
        admin = Administrador.query.filter_by(id_usuario=user.id_usuario).first()
        if admin:
            id_administrador = admin.id_administrador
    elif user.rol == "empleado":
        emp = Empleado.query.filter_by(id_usuario=user.id_usuario).first()
        if emp:
            id_empleado = emp.id_empleado

    return {
        "id": user.id_usuario,
        "id_usuario": user.id_usuario,
        "username": user.username,
        "rol": user.rol,
        "role": frontend_role(user.rol),
        "email": persona.email if persona else None,
        "nombre": persona.nombre if persona else None,
        "apellido": persona.apellido if persona else None,
        "nombre_completo": nombre_completo,
        "id_cliente": id_cliente,
        "id_administrador": id_administrador,
        "id_empleado": id_empleado,
    }


def _serialize_user_admin(usuario, persona):
    return {
        "id": usuario.id_usuario,
        "email": persona.email if persona else None,
        "role": frontend_role(usuario.rol),
        "rol": usuario.rol,
        "username": usuario.username,
        "nombre": persona.nombre if persona else None,
        "apellido": persona.apellido if persona else None,
        "ci": persona.ci if persona else None,
        "celular": persona.celular if persona else None,
    }


def _normalize_rol(value):
    if not value:
        return None
    key = str(value).strip().lower()
    return FRONTEND_TO_DB_ROLE.get(key, key if key in VALID_ROLES else None)


def _administrador_id_para_empleado():
    propio = Administrador.query.filter_by(id_usuario=g.current_user.id_usuario).first()
    if propio:
        return propio.id_administrador
    cualquiera = Administrador.query.first()
    return cualquiera.id_administrador if cualquiera else None


def _sync_rol_tablas(user, nuevo_rol):
    if nuevo_rol == "cliente":
        if not Cliente.query.filter_by(id_usuario=user.id_usuario).first():
            db.session.add(Cliente(
                id_usuario=user.id_usuario,
                fecha_afiliacion=date.today(),
            ))
    else:
        Cliente.query.filter_by(id_usuario=user.id_usuario).delete(synchronize_session=False)

    if nuevo_rol == "administrador":
        if not Administrador.query.filter_by(id_usuario=user.id_usuario).first():
            db.session.add(Administrador(
                nivel_acceso="parcial",
                fecha_designado=date.today(),
                area_responsabilidad="General",
                id_usuario=user.id_usuario,
            ))
    else:
        Administrador.query.filter_by(id_usuario=user.id_usuario).delete(synchronize_session=False)

    if nuevo_rol == "empleado":
        existente = Empleado.query.filter_by(id_usuario=user.id_usuario).first()
        if not existente:
            admin_id = _administrador_id_para_empleado()
            if not admin_id:
                raise ValueError("No hay un administrador al que asignar el empleado")
            db.session.add(Empleado(
                cargo="Sin asignar",
                turno_laboral="Mañana",
                fecha_contratacion=date.today(),
                salario=0,
                id_administrador=admin_id,
                id_usuario=user.id_usuario,
            ))
    else:
        Empleado.query.filter_by(id_usuario=user.id_usuario).update(
            {"id_usuario": None}, synchronize_session=False
        )


# ==========================================================
# AUTH - PÚBLICO
# ==========================================================

@auth_bp.route("/auth/login", methods=["POST"])
def login():
    data = _json()
    identifier = (data.get("email") or data.get("username") or "").strip()
    password = (data.get("contrasena") or data.get("password") or "").strip()

    if not identifier or not password:
        return jsonify({"error": "Se requiere username/email y contrasena"}), 400

    limpiar_tokens_expirados()

    max_intentos = int(current_app.config.get("MAX_LOGIN_ATTEMPTS", MAX_INTENTOS_LOGIN))
    bloqueo_minutos = int(current_app.config.get("BLOQUEO_MINUTOS", BLOQUEO_MINUTOS))
    ahora = datetime.now()

    user = Usuario.query.filter(Usuario.username.ilike(identifier)).first()
    if not user:
        persona = Persona.query.filter(Persona.email.ilike(identifier)).first()
        if persona:
            user = Usuario.query.filter_by(id_persona=persona.id_persona).first()

    # Respuesta genérica para no revelar qué cuentas existen.
    error_login = jsonify({"error": "Credenciales incorrectas"}), 401

    if not user:
        return error_login

    # Cuenta desactivada o bloqueada temporalmente: mismo mensaje genérico.
    if user.estado != "activo":
        return error_login

    if user.bloqueado_hasta and user.bloqueado_hasta.replace(tzinfo=None) > ahora:
        return error_login

    if not verify_password(user.contrasena, password):
        user.intentos_fallidos = (user.intentos_fallidos or 0) + 1
        if user.intentos_fallidos >= max_intentos:
            user.bloqueado_hasta = ahora + timedelta(minutes=bloqueo_minutos)
            user.intentos_fallidos = 0
        db.session.commit()
        return error_login

    # Éxito: se resetea el contador y el bloqueo.
    user.intentos_fallidos = 0
    user.bloqueado_hasta = None
    db.session.commit()

    if not user.contrasena.startswith(("pbkdf2:", "scrypt:", "argon2:")):
        user.contrasena = hash_password(password)
        db.session.commit()

    payload = _serialize_user(user)
    payload["token"] = create_token(user)
    return jsonify(payload), 200


@auth_bp.route("/auth/logout", methods=["POST"])
@require_auth()
def logout():
    token = _extract_bearer_token()
    if token:
        try:
            payload = decode_token(token, expected_type="access")
            revocar_token(
                payload.get("jti"),
                int(payload["sub"]),
                datetime.utcfromtimestamp(payload["exp"]),
            )
        except Exception:
            current_app.logger.exception("Error al revocar token en logout")
    return jsonify({"message": "Sesión cerrada"}), 200


@auth_bp.route("/auth/register", methods=["POST"])
def register():
    data = _json()
    nombre_in = (data.get("nombre") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("contrasena") or data.get("password") or ""
    apellido_in = data.get("apellido")
    ci_in = (data.get("ci") or "").strip() or None
    celular = (data.get("celular") or "").strip() or None
    username_in = (data.get("username") or "").strip() or None

    if not nombre_in or not email or not password:
        return jsonify({"error": "nombre, email y contrasena son obligatorios"}), 400
    if "@" not in email:
        return jsonify({"error": "email inválido"}), 400
    try:
        validar_password(password)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if Persona.query.filter(Persona.email.ilike(email)).first():
        return jsonify({"error": "El email ya está registrado"}), 409

    nombre, apellido = _split_nombre(nombre_in, apellido_in)
    username_base = username_in or email.split("@")[0]
    username = _unique_username(username_base)

    try:
        persona = Persona(
            nombre=nombre,
            apellido=apellido,
            ci=_unique_ci(ci_in),
            celular=celular,
            email=email,
        )
        db.session.add(persona)
        db.session.flush()

        usuario = Usuario(
            username=username,
            contrasena=hash_password(password),
            rol="cliente",
            id_persona=persona.id_persona,
        )
        db.session.add(usuario)
        db.session.flush()

        cliente = Cliente(
            id_usuario=usuario.id_usuario,
            fecha_afiliacion=date.today(),
        )
        db.session.add(cliente)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "No se pudo registrar: datos duplicados"}), 409
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Error en registro")
        return jsonify({"error": "No se pudo completar el registro"}), 500

    return jsonify({
        "message": "Usuario registrado",
        "user": _serialize_user(usuario),
    }), 201


@auth_bp.route("/auth/recover", methods=["POST"])
def recover():
    data = _json()
    email = (data.get("email") or "").strip()

    if not email:
        return jsonify({"error": "El email es obligatorio"}), 400

    persona = Persona.query.filter(Persona.email.ilike(email)).first()
    if persona:
        user = Usuario.query.filter_by(id_persona=persona.id_persona).first()
        if user and user.estado == "activo":
            token, jti, _ = create_reset_token(user)
            user.reset_token_jti = jti
            db.session.commit()
            frontend = current_app.config.get("FRONTEND_URL", "http://localhost:5173").rstrip("/")
            recover_url = f"{frontend}/reset-password/{token}"
            destino = persona.email

            if smtp_is_configured(current_app.config):
                try:
                    send_recovery_email(current_app.config, destino, recover_url)
                    current_app.logger.info("Correo de recuperación enviado a %s", destino)
                except Exception:
                    current_app.logger.exception("No se pudo enviar el correo de recuperación")
                    return jsonify({
                        "error": "No se pudo enviar el correo. Revisa la configuración SMTP."
                    }), 500
            else:
                current_app.logger.warning(
                    "SMTP no configurado. URL de recuperación para %s: %s", destino, recover_url
                )
                print(f"[AUTH RECOVER] SMTP no configurado. {destino} -> {recover_url}")

    return jsonify({
        "message": "Si el correo está registrado, se envió un enlace de recuperación."
    }), 200


@auth_bp.route("/auth/reset", methods=["POST"])
def reset():
    data = _json()
    token = (data.get("token") or "").strip()
    password = data.get("contrasena") or data.get("password") or data.get("nueva_contrasena") or ""

    if not token or not password:
        return jsonify({"error": "token y contrasena son obligatorios"}), 400
    try:
        validar_password(password)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        payload = decode_token(token, expected_type="reset")
    except Exception:
        return jsonify({"error": "El enlace es inválido o ha expirado"}), 400

    user = db.session.get(Usuario, int(payload["sub"]))
    if not user:
        return jsonify({"error": "El enlace es inválido o ha expirado"}), 400

    # Uso único: el token debe coincidir con el jti almacenado.
    if not user.reset_token_jti or user.reset_token_jti != payload.get("jti"):
        return jsonify({"error": "El enlace es inválido o ha expirado"}), 400

    user.contrasena = hash_password(password)
    user.reset_token_jti = None
    db.session.commit()
    return jsonify({"message": "Contraseña actualizada"}), 200


# ==========================================================
# ADMIN - GESTIÓN DE USUARIOS
# ==========================================================

@admin_bp.route("/admin/users", methods=["GET"])
@require_auth(roles=["administrador"])
def list_users():
    rows = (
        db.session.query(Usuario, Persona)
        .join(Persona, Usuario.id_persona == Persona.id_persona)
        .order_by(Usuario.id_usuario.asc())
        .all()
    )
    return jsonify([_serialize_user_admin(usuario, persona) for usuario, persona in rows]), 200


@admin_bp.route("/admin/users/<int:user_id>", methods=["PUT", "PATCH"])
@require_auth(roles=["administrador"])
def update_user(user_id):
    data = request.get_json(silent=True) or {}
    user = db.session.get(Usuario, user_id)
    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404

    persona = db.session.get(Persona, user.id_persona)
    if not persona:
        return jsonify({"error": "Persona no encontrada"}), 404

    nuevo_rol = _normalize_rol(data.get("rol") or data.get("role"))
    if "rol" in data or "role" in data:
        if not nuevo_rol:
            return jsonify({"error": "Rol inválido. Usa cliente, administrador o empleado"}), 400
        if user.id_usuario == g.current_user.id_usuario and nuevo_rol != user.rol:
            return jsonify({"error": "No puedes cambiar tu propio rol"}), 400
        if user.rol == "administrador" and nuevo_rol != "administrador":
            otros = Usuario.query.filter(
                Usuario.rol == "administrador",
                Usuario.id_usuario != user.id_usuario,
            ).count()
            if otros == 0:
                return jsonify({"error": "No puedes quitar el último administrador"}), 400

    estado = data.get("estado")
    if estado is not None:
        estado = str(estado).strip().lower()
        if estado not in ("activo", "inactivo"):
            return jsonify({"error": "Estado inválido. Usa activo o inactivo"}), 400
        if user.id_usuario == g.current_user.id_usuario and estado == "inactivo":
            return jsonify({"error": "No puedes desactivar tu propia cuenta"}), 400
        user.estado = estado
        if estado == "activo":
            user.intentos_fallidos = 0
            user.bloqueado_hasta = None

    nombre = data.get("nombre")
    apellido = data.get("apellido")
    ci = data.get("ci")
    celular = data.get("celular") if "celular" in data else persona.celular
    email = data.get("email")
    username = data.get("username")
    password = data.get("contrasena") or data.get("password")

    if nombre is not None:
        nombre = str(nombre).strip()
        if not nombre:
            return jsonify({"error": "El nombre no puede estar vacío"}), 400
        persona.nombre = nombre[:80]
    if apellido is not None:
        apellido = str(apellido).strip()
        if not apellido:
            return jsonify({"error": "El apellido no puede estar vacío"}), 400
        persona.apellido = apellido[:80]
    if ci is not None:
        ci = str(ci).strip()
        if not ci:
            return jsonify({"error": "El CI no puede estar vacío"}), 400
        duplicado = Persona.query.filter(Persona.ci == ci, Persona.id_persona != persona.id_persona).first()
        if duplicado:
            return jsonify({"error": "Ese CI ya está registrado"}), 409
        persona.ci = ci[:20]
    if "celular" in data:
        persona.celular = (str(celular).strip()[:20] if celular else None)
    if email is not None:
        email = str(email).strip().lower()
        if email and "@" not in email:
            return jsonify({"error": "email inválido"}), 400
        if email:
            duplicado = Persona.query.filter(
                Persona.email.ilike(email),
                Persona.id_persona != persona.id_persona,
            ).first()
            if duplicado:
                return jsonify({"error": "Ese email ya está registrado"}), 409
        persona.email = email or None
    if username is not None:
        username = str(username).strip()
        if not username:
            return jsonify({"error": "El username no puede estar vacío"}), 400
        duplicado = Usuario.query.filter(
            Usuario.username.ilike(username),
            Usuario.id_usuario != user.id_usuario,
        ).first()
        if duplicado:
            return jsonify({"error": "Ese username ya está registrado"}), 409
        user.username = username[:50]
    if password:
        try:
            validar_password(str(password))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        user.contrasena = hash_password(str(password))

    try:
        if nuevo_rol and nuevo_rol != user.rol:
            _sync_rol_tablas(user, nuevo_rol)
            user.rol = nuevo_rol
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "error": "No se pudo actualizar: el rol tiene registros relacionados (reservas, canchas, etc.)."
        }), 409
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Error al actualizar usuario")
        return jsonify({"error": "No se pudo actualizar el usuario"}), 500

    db.session.refresh(user)
    db.session.refresh(persona)
    return jsonify(_serialize_user_admin(user, persona)), 200


@admin_bp.route("/admin/users/<int:user_id>", methods=["DELETE"])
@require_auth(roles=["administrador"])
def delete_user(user_id):
    if g.current_user.id_usuario == user_id:
        return jsonify({"error": "No puedes eliminar tu propia cuenta"}), 400

    user = db.session.get(Usuario, user_id)
    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404

    persona_id = user.id_persona
    try:
        Cliente.query.filter_by(id_usuario=user.id_usuario).delete(synchronize_session=False)
        Administrador.query.filter_by(id_usuario=user.id_usuario).delete(synchronize_session=False)
        Empleado.query.filter_by(id_usuario=user.id_usuario).update(
            {"id_usuario": None}, synchronize_session=False
        )
        db.session.delete(user)
        persona = db.session.get(Persona, persona_id)
        if persona:
            db.session.delete(persona)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        # El usuario tiene historial (reservas, etc.): se DESACTIVA en vez de borrarlo.
        user = db.session.get(Usuario, user_id)
        if user:
            user.estado = "inactivo"
            db.session.commit()
            return jsonify({
                "message": "El usuario tiene registros relacionados. Se desactivó la cuenta (no se borra)."
            }), 200
        return jsonify({
            "error": "No se puede eliminar el usuario porque tiene registros relacionados (reservas u otros)."
        }), 409
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Error al eliminar usuario")
        return jsonify({"error": "No se pudo eliminar el usuario"}), 500

    return jsonify({"message": "Usuario eliminado"}), 200


# ==========================================================
# REGISTRO DEL MÓDULO EN LA APP
# ==========================================================

def register_auth(app):
    """Configura SMTP/JWT y registra auth_bp y admin_bp (con y sin prefijo /api)."""
    from pathlib import Path
    import os
    from dotenv import load_dotenv

    config_dir = Path(__file__).resolve().parent.parent / "config"
    load_dotenv(config_dir / "correo.env")

    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")
    app.config["JWT_EXPIRES_HOURS"] = int(os.getenv("JWT_EXPIRES_HOURS", "12"))
    app.config["RESET_TOKEN_EXPIRES_SECONDS"] = int(
        os.getenv("RESET_TOKEN_EXPIRES_SECONDS", "1800")
    )
    app.config["MAX_LOGIN_ATTEMPTS"] = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
    app.config["BLOQUEO_MINUTOS"] = int(os.getenv("BLOQUEO_MINUTOS", "15"))
    app.config["FRONTEND_URL"] = os.getenv("FRONTEND_URL", "http://localhost:5173")
    app.config["SMTP_HOST"] = os.getenv("SMTP_HOST", "").strip()
    app.config["SMTP_PORT"] = os.getenv("SMTP_PORT", "587").strip()
    app.config["SMTP_USER"] = os.getenv("SMTP_USER", "").strip()
    app.config["SMTP_PASSWORD"] = os.getenv("SMTP_PASSWORD", "").strip()
    app.config["SMTP_FROM"] = os.getenv("SMTP_FROM", "").strip()
    app.config["SMTP_USE_TLS"] = os.getenv("SMTP_USE_TLS", "true").strip()
    app.config["SMTP_USE_SSL"] = os.getenv("SMTP_USE_SSL", "false").strip()

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(auth_bp, url_prefix="/api", name="auth_api")
    app.register_blueprint(admin_bp, url_prefix="/api", name="admin_api")

    if smtp_is_configured(app.config):
        app.logger.info("SMTP configurado: los correos de recuperación se enviarán por email.")
    else:
        app.logger.warning(
            "SMTP no configurado. La recuperación de contraseña se imprimirá en la consola."
        )