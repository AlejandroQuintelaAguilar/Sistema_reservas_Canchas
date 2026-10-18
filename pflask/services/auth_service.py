from datetime import datetime, timedelta, timezone
from functools import wraps
from uuid import uuid4

import jwt
from flask import current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models.token_revocado import TokenRevocado
from models.usuario import Usuario

ROLE_TO_FRONTEND = {
    "administrador": "admin",
    "cliente": "user",
    "empleado": "empleado",
}

MAX_INTENTOS_LOGIN = 5
BLOQUEO_MINUTOS = 15


def hash_password(plain_password):
    return generate_password_hash(plain_password, method="pbkdf2:sha256")


def verify_password(stored, plain_password):
    if not stored or not plain_password:
        return False
    stored = stored.strip() if isinstance(stored, str) else stored
    plain_password = plain_password.strip() if isinstance(plain_password, str) else plain_password
    if stored.startswith(("pbkdf2:", "scrypt:", "argon2:")):
        return check_password_hash(stored, plain_password)
    return stored == plain_password


def frontend_role(rol):
    return ROLE_TO_FRONTEND.get(rol, rol)


def create_token(user, token_type="access", expires_delta=None, jti=None):
    if expires_delta is None:
        hours = int(current_app.config.get("JWT_EXPIRES_HOURS", 12))
        expires_delta = timedelta(hours=hours)

    if not jti:
        jti = str(uuid4())

    payload = {
        "sub": str(user.id_usuario),
        "rol": user.rol,
        "username": user.username,
        "type": token_type,
        "jti": jti,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + expires_delta,
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def create_reset_token(user):
    seconds = int(current_app.config.get("RESET_TOKEN_EXPIRES_SECONDS", 1800))
    jti = str(uuid4())
    token = create_token(user, token_type="reset", expires_delta=timedelta(seconds=seconds), jti=jti)
    return token, jti, seconds


def decode_token(token, expected_type="access"):
    payload = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("Tipo de token inválido")
    return payload


def _extract_bearer_token():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    return header.split(" ", 1)[1].strip() or None


def usuario_opcional():
    """Usuario de la peticion si trae un token valido; None si es anonimo.

    No se apoya en g.current_user porque g pertenece al contexto de aplicacion
    y puede quedar contaminado entre peticiones cuando alguien empuja un app
    context a mano (scripts, pruebas, workers).
    """
    token = _extract_bearer_token()
    if not token:
        return None
    try:
        payload = decode_token(token, expected_type="access")
    except jwt.InvalidTokenError:
        return None
    if _esta_revocado(payload.get("jti")):
        return None
    try:
        user = db.session.get(Usuario, int(payload["sub"]))
    except (KeyError, TypeError, ValueError):
        return None
    if not user or user.estado != "activo":
        return None
    return user


def limpiar_tokens_expirados():
    ahora = datetime.now(timezone.utc).replace(tzinfo=None)
    TokenRevocado.query.filter(TokenRevocado.expiracion < ahora).delete(
        synchronize_session=False
    )
    db.session.commit()


def revocar_token(jti, id_usuario, expiracion):
    if not jti:
        return
    token = TokenRevocado.query.filter_by(jti=jti).first()
    if token:
        return
    db.session.add(
        TokenRevocado(
            jti=jti,
            id_usuario=id_usuario,
            expiracion=expiracion.replace(tzinfo=None)
            if expiracion.tzinfo
            else expiracion,
            fecha_revocacion=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )
    db.session.commit()


def _esta_revocado(jti):
    if not jti:
        return False
    return TokenRevocado.query.filter_by(jti=jti).first() is not None


def require_auth(roles=None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            token = _extract_bearer_token()
            if not token:
                return jsonify({"error": "No autenticado"}), 401
            try:
                payload = decode_token(token, expected_type="access")
            except jwt.ExpiredSignatureError:
                return jsonify({"error": "Token expirado"}), 401
            except jwt.InvalidTokenError:
                return jsonify({"error": "Token inválido"}), 401

            if _esta_revocado(payload.get("jti")):
                return jsonify({"error": "Sesión cerrada. Inicia sesión de nuevo."}), 401

            user = db.session.get(Usuario, int(payload["sub"]))
            if not user:
                return jsonify({"error": "Usuario no encontrado"}), 401
            if user.estado != "activo":
                return jsonify({"error": "Cuenta desactivada"}), 401
            if roles and user.rol not in roles:
                return jsonify({"error": "No autorizado"}), 403

            g.current_user = user
            return fn(*args, **kwargs)

        return wrapper

    return decorator