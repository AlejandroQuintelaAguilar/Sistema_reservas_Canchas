from flask import Blueprint, jsonify, request

from extensions import db
from services import notificaciones_service as servicio
from services.auth_service import require_auth
from utils.responses import error_json

notificaciones_bp = Blueprint("notificaciones", __name__, url_prefix="/api/notificaciones")


def _id_admin_actual():
    from flask import g
    return getattr(getattr(g, "current_user", None), "id_usuario", None)


# =====================================================================
# PLANTILLAS (administrador)
# =====================================================================
@notificaciones_bp.get("/plantillas")
@require_auth(roles=["administrador"])
def listar_plantillas():
    try:
        plantillas = servicio.listar_plantillas(
            tipo=request.args.get("tipo"),
            canal=request.args.get("canal"),
            incluir_inactivas=request.args.get("incluir_inactivas") == "1",
        )
        return jsonify([p.to_dict() for p in plantillas]), 200
    except ValueError as e:
        return error_json(str(e), codigo=400)
    except Exception as e:  # noqa: BLE001
        db.session.rollback()
        return error_json("Error al listar las plantillas.", str(e), 500)


@notificaciones_bp.get("/plantillas/<int:id_plantilla>")
@require_auth(roles=["administrador"])
def obtener_plantilla(id_plantilla):
    try:
        return jsonify(servicio.obtener_plantilla(id_plantilla).to_dict()), 200
    except ValueError as e:
        return error_json(str(e), codigo=404)


@notificaciones_bp.post("/plantillas")
@require_auth(roles=["administrador"])
def crear_plantilla():
    try:
        plantilla = servicio.crear_plantilla(
            request.get_json(silent=True) or {}, _id_admin_actual()
        )
        return jsonify(plantilla.to_dict()), 201
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e), codigo=400)
    except Exception as e:  # noqa: BLE001
        db.session.rollback()
        return error_json("Error al crear la plantilla.", str(e), 500)


@notificaciones_bp.put("/plantillas/<int:id_plantilla>")
@require_auth(roles=["administrador"])
def actualizar_plantilla(id_plantilla):
    try:
        plantilla = servicio.actualizar_plantilla(
            id_plantilla, request.get_json(silent=True) or {}
        )
        return jsonify(plantilla.to_dict()), 200
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e), codigo=400)
    except Exception as e:  # noqa: BLE001
        db.session.rollback()
        return error_json("Error al actualizar la plantilla.", str(e), 500)


@notificaciones_bp.delete("/plantillas/<int:id_plantilla>")
@require_auth(roles=["administrador"])
def eliminar_plantilla(id_plantilla):
    try:
        servicio.eliminar_plantilla(id_plantilla)
        return jsonify({"mensaje": "Plantilla eliminada."}), 200
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e), codigo=404)
    except Exception as e:  # noqa: BLE001
        db.session.rollback()
        return error_json("Error al eliminar la plantilla.", str(e), 500)


# =====================================================================
# HISTORIAL DE NOTIFICACIONES (administrador)
# =====================================================================
@notificaciones_bp.get("")
@require_auth(roles=["administrador"])
def listar_notificaciones():
    try:
        estado = request.args.get("estado")
        if estado and estado not in ("pendiente", "enviado", "fallido"):
            return error_json("Estado no válido. Use: pendiente, enviado o fallido.", codigo=400)
        notificaciones = servicio.listar_notificaciones(
            estado=estado,
            tipo=request.args.get("tipo"),
            id_reserva=request.args.get("id_reserva"),
            limite=request.args.get("limite", 100),
        )
        return jsonify([n.to_dict() for n in notificaciones]), 200
    except ValueError as e:
        return error_json(str(e), codigo=400)
    except Exception as e:  # noqa: BLE001
        db.session.rollback()
        return error_json("Error al listar las notificaciones.", str(e), 500)


@notificaciones_bp.get("/<int:id_notificacion>")
@require_auth(roles=["administrador"])
def obtener_notificacion(id_notificacion):
    try:
        notificacion = servicio.obtener_notificacion(id_notificacion)
        return jsonify(notificacion.to_dict(con_historial=True)), 200
    except ValueError as e:
        return error_json(str(e), codigo=404)
    except Exception as e:  # noqa: BLE001
        db.session.rollback()
        return error_json("Error al obtener la notificacion.", str(e), 500)


@notificaciones_bp.post("/<int:id_notificacion>/reintentar")
@require_auth(roles=["administrador"])
def reintentar_notificacion(id_notificacion):
    try:
        notificacion = servicio.reintentar(id_notificacion)
        return jsonify({
            "mensaje": "Notificacion reencolada.",
            "notificacion": notificacion.to_dict(),
        }), 200
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e), codigo=400)
    except Exception as e:  # noqa: BLE001
        db.session.rollback()
        return error_json("Error al reencolar la notificacion.", str(e), 500)


# =====================================================================
# OPERACION
# =====================================================================
@notificaciones_bp.post("/enviar-pendientes")
@require_auth(roles=["administrador"])
def enviar_pendientes():
    """Fuerza un pase del worker a mano, util para probar y para no depender
    del temporizador."""
    try:
        resultado = servicio.enviar_pendientes(
            limite=request.args.get("limite", 20, type=int)
        )
        return jsonify({"mensaje": "Pase de envio terminado.", "resultado": resultado}), 200
    except Exception as e:  # noqa: BLE001
        db.session.rollback()
        return error_json("Error al enviar las notificaciones.", str(e), 500)


@notificaciones_bp.post("/generar-recordatorios")
@require_auth(roles=["administrador"])
def generar_recordatorios():
    try:
        creadas = servicio.generar_recordatorios()
        return jsonify({
            "mensaje": f"{creadas} recordatorio(s) encolado(s).",
            "creadas": creadas,
        }), 200
    except Exception as e:  # noqa: BLE001
        db.session.rollback()
        return error_json("Error al generar los recordatorios.", str(e), 500)
