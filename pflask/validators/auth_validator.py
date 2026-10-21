import re

VALID_ROLES = ("cliente", "administrador", "empleado")

PASSWORD_MIN = 8
PASSWORD_MAX = 128
_RE_MAYUSCULA = re.compile(r"[A-ZÁÉÍÓÚÑ]")
_RE_MINUSCULA = re.compile(r"[a-záéíóúñ]")
_RE_DIGITO = re.compile(r"\d")
_RE_SIMBOLO = re.compile(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?`~]")

# Mismos formatos que src/utils/validaciones.js (CI_RE y CELULAR_RE).
_RE_CI = re.compile(r"^[0-9]{4,10}$")
_RE_CELULAR = re.compile(r"^\+?[0-9]{7,15}$")


def validar_password(password):
    """Aplica la misma politica que el frontend en src/utils/validaciones.js.

    Sin esto la regla completa era solo cosmetica: un POST directo a la API
    aceptaba '12345678' como contrasena valida.
    """
    if not isinstance(password, str) or not password:
        raise ValueError("La contrasena es obligatoria")
    if len(password) < PASSWORD_MIN:
        raise ValueError(
            f"La contrasena debe tener al menos {PASSWORD_MIN} caracteres"
        )
    if len(password) > PASSWORD_MAX:
        raise ValueError(
            f"La contrasena no puede superar {PASSWORD_MAX} caracteres"
        )
    if not _RE_MAYUSCULA.search(password):
        raise ValueError("La contrasena debe incluir al menos una letra mayuscula")
    if not _RE_MINUSCULA.search(password):
        raise ValueError("La contrasena debe incluir al menos una letra minuscula")
    if not _RE_DIGITO.search(password):
        raise ValueError("La contrasena debe incluir al menos un numero")
    if not _RE_SIMBOLO.search(password):
        raise ValueError("La contrasena debe incluir al menos un simbolo")
    return password


def password_requerido(password, campo="contrasena"):
    """Como validar_password pero devuelve None si el campo viene vacio."""
    if password is None or password == "":
        raise ValueError(f"{campo} es obligatorio")
    return validar_password(password)


def validar_ci(ci, obligatorio=False):
    """CI: solo digitos, de 4 a 10. Devuelve el valor limpio o None.

    Sin esto un POST directo a la API guardaba 'abc' como CI: el formato solo
    se revisaba en el frontend.
    """
    if ci is None:
        if obligatorio:
            raise ValueError("El CI es obligatorio")
        return None
    ci = str(ci).strip()
    if not ci:
        if obligatorio:
            raise ValueError("El CI es obligatorio")
        return None
    if not _RE_CI.match(ci):
        raise ValueError("El CI debe tener entre 4 y 10 digitos, sin letras")
    return ci


def validar_celular(celular, obligatorio=False):
    """Celular: 7 a 15 digitos, con '+' inicial opcional. Devuelve valor o None."""
    if celular is None:
        if obligatorio:
            raise ValueError("El celular es obligatorio")
        return None
    celular = str(celular).strip()
    if not celular:
        if obligatorio:
            raise ValueError("El celular es obligatorio")
        return None
    if not _RE_CELULAR.match(celular):
        raise ValueError("El celular debe tener entre 7 y 15 digitos")
    return celular


def validar_login(data):
    """Valida el cuerpo de POST /auth/login. Devuelve identifier y password."""
    if not isinstance(data, dict):
        raise ValueError("El cuerpo de la solicitud debe ser un objeto JSON válido.")

    identifier = (data.get("email") or data.get("username") or "").strip()
    password = (data.get("contrasena") or data.get("password") or "").strip()

    if not identifier or not password:
        raise ValueError("Se requiere username/email y contrasena")

    return {"identifier": identifier, "password": password}


def validar_registro(data):
    """Valida el cuerpo de POST /auth/register. Devuelve datos limpios."""
    if not isinstance(data, dict):
        raise ValueError("El cuerpo de la solicitud debe ser un objeto JSON válido.")

    nombre_in = (data.get("nombre") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("contrasena") or data.get("password") or ""
    apellido_in = data.get("apellido")
    ci_in = (data.get("ci") or "").strip() or None
    celular = (data.get("celular") or "").strip() or None
    username_in = (data.get("username") or "").strip() or None

    if not nombre_in or not email or not password:
        raise ValueError("nombre, email y contrasena son obligatorios")
    if "@" not in email:
        raise ValueError("email inválido")
    validar_password(password)

    return {
        "nombre": nombre_in,
        "apellido": apellido_in,
        "email": email,
        "password": password,
        "ci": ci_in,
        "celular": celular,
        "username": username_in,
    }


def validar_recuperacion(data):
    """Valida el cuerpo de POST /auth/recover. Devuelve el email."""
    if not isinstance(data, dict):
        raise ValueError("El cuerpo de la solicitud debe ser un objeto JSON válido.")

    email = (data.get("email") or "").strip()

    if not email:
        raise ValueError("El email es obligatorio")

    return email


def validar_reset(data):
    """Valida el cuerpo de POST /auth/reset. Devuelve token y password."""
    if not isinstance(data, dict):
        raise ValueError("El cuerpo de la solicitud debe ser un objeto JSON válido.")

    token = (data.get("token") or "").strip()
    password = data.get("contrasena") or data.get("password") or data.get("nueva_contrasena") or ""

    if not token or not password:
        raise ValueError("token y contrasena son obligatorios")
    validar_password(password)

    return {"token": token, "password": str(password)}


def validar_rol(value):
    """Normaliza un nombre de rol desde el frontend ('admin', 'user', 'empleado', ...)."""
    if not value:
        return None
    key = str(value).strip().lower()
    FRONTEND_TO_DB = {
        "admin": "administrador",
        "user": "cliente",
        "empleado": "empleado",
        "administrador": "administrador",
        "cliente": "cliente",
    }
    return FRONTEND_TO_DB.get(key, key if key in VALID_ROLES else None)