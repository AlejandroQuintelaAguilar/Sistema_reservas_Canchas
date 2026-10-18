from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy.exc import IntegrityError

from extensions import db
from services import reservas_service
from services.auth_service import require_auth
from utils.responses import error_json

reservas_bp = Blueprint("reservas", __name__, url_prefix="/api")


def _codigo_error(exc):
    mensaje = str(exc).lower()
    if "no encontrada" in mensaje or "no existe" in mensaje:
        return 404
    if "ya existe" in mensaje or "duplicado" in mensaje:
        return 409
    return 400


def _es_conflicto_reserva(exc):
    """Detecta el violación de la restricción EXCLUDE anti-solape de la BD."""
    return "ex_reserva_solapamiento" in str(getattr(exc, "orig", exc)).lower()


def _datos():
    return request.get_json(silent=True) or {}


# ============================================================
# CLIENTES (público de staff; la creación es admin/empleado)
# ============================================================
@reservas_bp.get("/clientes")
@require_auth(roles=["administrador", "empleado"])
def listar_clientes():
    try:
        return jsonify(reservas_service.listar_clientes()), 200
    except Exception as e:
        current_app.logger.exception("Error al listar clientes")
        return error_json("Error interno al obtener clientes.", str(e), 500)


@reservas_bp.post("/admin/clientes")
@require_auth(roles=["administrador", "empleado"])
def crear_cliente():
    try:
        return jsonify(reservas_service.crear_cliente(_datos())), 201
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e), codigo=_codigo_error(e))
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error al crear cliente")
        return error_json("Error al registrar cliente.", str(e), 500)


# ============================================================
# RESERVAS (cliente)
# ============================================================
@reservas_bp.get("/reservas/historial")
@require_auth()
def historial_reservas():
    try:
        id_cliente = reservas_service.obtener_id_cliente_actual(
            getattr(g, "current_user", None)
        )
        return jsonify(reservas_service.listar_reservas_historial(id_cliente)), 200
    except ValueError as e:
        return error_json(str(e), codigo=_codigo_error(e))
    except Exception as e:
        return error_json("Error interno al obtener el historial.", str(e), 500)


@reservas_bp.get("/reservas/<int:id_cliente>")
@require_auth()
def get_reservas_cliente(id_cliente):
    try:
        return jsonify(reservas_service.listar_reservas_cliente(id_cliente)), 200
    except Exception as e:
        return error_json("Error interno al obtener reservas.", str(e), 500)


@reservas_bp.get("/reservas/<int:id_cliente>/vigentes")
@require_auth()
def get_reservas_vigentes(id_cliente):
    try:
        return jsonify(
            reservas_service.listar_reservas_cliente(id_cliente, vigentes=True)
        ), 200
    except Exception as e:
        return error_json("Error interno al obtener reservas vigentes.", str(e), 500)


@reservas_bp.post("/reservas")
@require_auth()
def crear_reserva():
    try:
        resultado = reservas_service.crear_reserva(
            _datos(), current_user=getattr(g, "current_user", None)
        )
        return jsonify(resultado), 201
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e), codigo=_codigo_error(e))
    except IntegrityError as e:
        db.session.rollback()
        if _es_conflicto_reserva(e):
            return error_json(
                "La cancha no está disponible en ese horario (validado por la base de datos).",
                codigo=409,
            )
        current_app.logger.exception("Error de integridad al crear reserva")
        return error_json("Error al procesar la reserva.", str(e), 500)
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error al crear reserva")
        return error_json("Error al procesar la reserva.", str(e), 500)


@reservas_bp.put("/reservas/<int:id_reserva>/cancelar")
@require_auth()
def cancelar_reserva(id_reserva):
    try:
        resultado = reservas_service.cancelar_reserva(
            id_reserva, _datos().get("motivo"),
            id_usuario=getattr(g.current_user, "id_usuario", None),
        )
        return jsonify(resultado), 200
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e), codigo=_codigo_error(e))
    except Exception as e:
        db.session.rollback()
        return error_json("Error al cancelar la reserva.", str(e), 500)


@reservas_bp.post("/reservas/<int:id_reserva>/pagar")
@require_auth()
def pagar_reserva(id_reserva):
    try:
        datos = _datos()
        resultado = reservas_service.pagar_reserva(
            id_reserva, datos.get("metodo_pago"),
            id_usuario=getattr(g.current_user, "id_usuario", None),
            referencia=datos.get("referencia"),
        )
        return jsonify(resultado), 201
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e), codigo=_codigo_error(e))
    except Exception as e:
        db.session.rollback()
        return error_json("Error al procesar el pago.", str(e), 500)


# ============================================================
# RESERVAS (admin / empleado)
# ============================================================
@reservas_bp.get("/admin/reservas")
@require_auth(roles=["administrador", "empleado"])
def get_todas_reservas():
    try:
        resultado = reservas_service.listar_reservas_admin(
            fecha=request.args.get("fecha"),
            estado=request.args.get("estado"),
            id_cancha=request.args.get("id_cancha"),
        )
        return jsonify(resultado), 200
    except ValueError as e:
        return error_json(str(e), codigo=_codigo_error(e))
    except Exception as e:
        return error_json("Error interno al obtener reservas.", str(e), 500)


@reservas_bp.put("/admin/reservas/<int:id_reserva>/cancelar-admin")
@require_auth(roles=["administrador", "empleado"])
def cancelar_reserva_admin(id_reserva):
    try:
        resultado = reservas_service.cancelar_reserva_admin(
            id_reserva, _datos().get("motivo"),
            id_usuario=getattr(g.current_user, "id_usuario", None),
        )
        return jsonify(resultado), 200
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e), codigo=_codigo_error(e))
    except Exception as e:
        db.session.rollback()
        return error_json("Error al cancelar la reserva.", str(e), 500)


@reservas_bp.put("/admin/reservas/<int:id_reserva>/modificar-admin")
@require_auth(roles=["administrador", "empleado"])
def modificar_reserva_admin(id_reserva):
    try:
        resultado = reservas_service.modificar_reserva_admin(
            id_reserva, _datos(),
            id_usuario=getattr(g.current_user, "id_usuario", None),
        )
        return jsonify(resultado), 200
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e), codigo=_codigo_error(e))
    except IntegrityError as e:
        db.session.rollback()
        if _es_conflicto_reserva(e):
            return error_json(
                "La cancha no está disponible en el nuevo horario "
                "(validado por la base de datos).",
                codigo=409,
            )
        return error_json("Error al modificar la reserva.", str(e), 500)
    except Exception as e:
        db.session.rollback()
        return error_json("Error al modificar la reserva.", str(e), 500)


@reservas_bp.get("/admin/reservas/<int:id_reserva>/historial")
@require_auth(roles=["administrador", "empleado"])
def historial_reserva(id_reserva):
    try:
        return jsonify(reservas_service.listar_historial_reserva(id_reserva)), 200
    except ValueError as e:
        return error_json(str(e), codigo=_codigo_error(e))
    except Exception as e:
        return error_json("Error interno al obtener el historial.", str(e), 500)


@reservas_bp.post("/empleado/reservas")
@require_auth(roles=["administrador", "empleado"])
def crear_reserva_presencial():
    try:
        resultado = reservas_service.crear_reserva_presencial(
            _datos(), current_user=getattr(g, "current_user", None)
        )
        return jsonify(resultado), 201
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e), codigo=_codigo_error(e))
    except IntegrityError as e:
        db.session.rollback()
        if _es_conflicto_reserva(e):
            return error_json(
                "La cancha no está disponible en ese horario (validado por la base de datos).",
                codigo=409,
            )
        current_app.logger.exception("Error de integridad en reserva presencial")
        return error_json("Error al procesar la reserva presencial.", str(e), 500)
    except Exception as e:
        db.session.rollback()
        return error_json("Error al procesar la reserva presencial.", str(e), 500)


# ============================================================
# BLOQUEOS
# ============================================================
@reservas_bp.get("/bloqueos")
@require_auth()
def get_bloqueos():
    try:
        activos = request.args.get("activos", "true").lower() != "false"
        return jsonify(reservas_service.listar_bloqueos(activos)), 200
    except Exception as e:
        return error_json("Error interno al obtener bloqueos.", str(e), 500)


@reservas_bp.post("/admin/bloqueos")
@require_auth(roles=["administrador"])
def crear_bloqueo():
    try:
        return jsonify(
            reservas_service.crear_bloqueo(
                _datos(), id_usuario=getattr(g.current_user, "id_usuario", None)
            )
        ), 201
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e), codigo=_codigo_error(e))
    except Exception as e:
        db.session.rollback()
        return error_json("Error al crear bloqueo.", str(e), 500)


@reservas_bp.delete("/admin/bloqueos/<int:id_bloqueo>")
@require_auth(roles=["administrador"])
def eliminar_bloqueo(id_bloqueo):
    try:
        return jsonify(reservas_service.eliminar_bloqueo(id_bloqueo)), 200
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e), codigo=_codigo_error(e))
    except Exception as e:
        db.session.rollback()
        return error_json("Error al eliminar bloqueo.", str(e), 500)


# ============================================================
# CRUD CANCHAS (admin)
# ============================================================
@reservas_bp.post("/admin/canchas")
@require_auth(roles=["administrador"])
def admin_crear_cancha():
    try:
        return jsonify(
            reservas_service.admin_crear_cancha(
                _datos(), id_usuario=getattr(g.current_user, "id_usuario", None)
            )
        ), 201
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e), codigo=_codigo_error(e))
    except Exception as e:
        db.session.rollback()
        return error_json("Error al crear cancha.", str(e), 500)


@reservas_bp.put("/admin/canchas/<int:id_cancha>")
@require_auth(roles=["administrador"])
def admin_editar_cancha(id_cancha):
    try:
        return jsonify(reservas_service.admin_editar_cancha(
            id_cancha, _datos(), id_usuario=getattr(g, "current_user", None).id_usuario
        )), 200
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e), codigo=_codigo_error(e))
    except Exception as e:
        db.session.rollback()
        return error_json("Error al editar cancha.", str(e), 500)


@reservas_bp.delete("/admin/canchas/<int:id_cancha>")
@require_auth(roles=["administrador"])
def admin_eliminar_cancha(id_cancha):
    try:
        return jsonify(reservas_service.admin_eliminar_cancha(
            id_cancha, id_usuario=getattr(g, "current_user", None).id_usuario
        )), 200
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e), codigo=_codigo_error(e))
    except Exception as e:
        db.session.rollback()
        return error_json("Error al eliminar cancha.", str(e), 500)


# ============================================================
# CRUD CATEGORÍAS (admin)
# ============================================================
@reservas_bp.post("/admin/categorias")
@require_auth(roles=["administrador"])
def admin_crear_categoria():
    try:
        return jsonify(reservas_service.admin_crear_categoria(_datos())), 201
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e), codigo=_codigo_error(e))
    except Exception as e:
        db.session.rollback()
        return error_json("Error al crear categoría.", str(e), 500)


@reservas_bp.put("/admin/categorias/<int:id_categoria>")
@require_auth(roles=["administrador"])
def admin_editar_categoria(id_categoria):
    try:
        return jsonify(
            reservas_service.admin_editar_categoria(id_categoria, _datos())
        ), 200
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e), codigo=_codigo_error(e))
    except Exception as e:
        db.session.rollback()
        return error_json("Error al editar categoría.", str(e), 500)


@reservas_bp.delete("/admin/categorias/<int:id_categoria>")
@require_auth(roles=["administrador"])
def admin_eliminar_categoria(id_categoria):
    try:
        return jsonify(reservas_service.admin_eliminar_categoria(id_categoria)), 200
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e), codigo=_codigo_error(e))
    except Exception as e:
        db.session.rollback()
        return error_json("Error al eliminar categoría.", str(e), 500)