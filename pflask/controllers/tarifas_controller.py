from flask import Blueprint, g, jsonify, request

from services import tarifas_service
from services.auth_service import require_auth
from utils.responses import error_json

tarifas_bp = Blueprint("tarifas", __name__, url_prefix="/api")


def _datos():
    return request.get_json(silent=True) or {}


def _uid():
    return getattr(g, "current_user", None).id_usuario


# ============================================================
# LECTURA (público)
# ============================================================
@tarifas_bp.get("/canchas/<int:id_cancha>/tarifas")
def listar_tarifas_cancha(id_cancha):
    try:
        solo_activas = request.args.get("todas", "false").lower() != "true"
        return jsonify(tarifas_service.listar_tarifas(id_cancha, solo_activas)), 200
    except ValueError as e:
        return error_json(str(e), codigo=404)
    except Exception as e:
        return error_json("Error interno al obtener tarifas.", str(e), 500)


@tarifas_bp.get("/tarifas")
def listar_todas_las_tarifas():
    try:
        solo_activas = request.args.get("todas", "false").lower() != "true"
        return jsonify(tarifas_service.listar_todas_tarifas(solo_activas)), 200
    except Exception as e:
        return error_json("Error interno al obtener tarifas.", str(e), 500)


@tarifas_bp.get("/canchas/<int:id_cancha>/horarios")
def listar_horarios_cancha(id_cancha):
    try:
        return jsonify(tarifas_service.listar_horarios(id_cancha)), 200
    except ValueError as e:
        return error_json(str(e), codigo=404)
    except Exception as e:
        return error_json("Error interno al obtener horarios.", str(e), 500)


# ============================================================
# ADMINISTRACION DE HORARIOS
# ============================================================
@tarifas_bp.put("/admin/canchas/<int:id_cancha>/horarios")
@require_auth(roles=["administrador"])
def actualizar_horarios(id_cancha):
    try:
        return jsonify(
            tarifas_service.aplicar_horarios(id_cancha, _datos().get("horarios"), _uid())
        ), 200
    except ValueError as e:
        return error_json(str(e))
    except Exception as e:
        return error_json("Error al guardar los horarios.", str(e), 500)


# ============================================================
# ADMINISTRACION DE TARIFAS
# ============================================================
@tarifas_bp.post("/admin/tarifas")
@require_auth(roles=["administrador"])
def crear_tarifa():
    try:
        return jsonify(tarifas_service.crear_tarifa(_datos(), _uid())), 201
    except ValueError as e:
        return error_json(str(e))
    except Exception as e:
        return error_json("Error al crear la tarifa.", str(e), 500)


@tarifas_bp.put("/admin/tarifas/<int:id_tarifa>")
@require_auth(roles=["administrador"])
def actualizar_tarifa(id_tarifa):
    try:
        return jsonify(tarifas_service.actualizar_tarifa(id_tarifa, _datos(), _uid())), 200
    except ValueError as e:
        return error_json(str(e))
    except Exception as e:
        return error_json("Error al actualizar la tarifa.", str(e), 500)


@tarifas_bp.delete("/admin/tarifas/<int:id_tarifa>")
@require_auth(roles=["administrador"])
def eliminar_tarifa(id_tarifa):
    try:
        return jsonify(tarifas_service.eliminar_tarifa(id_tarifa, _uid())), 200
    except ValueError as e:
        return error_json(str(e))
    except Exception as e:
        return error_json("Error al eliminar la tarifa.", str(e), 500)


@tarifas_bp.delete("/admin/canchas/<int:id_cancha>/tarifas")
@require_auth(roles=["administrador"])
def eliminar_tarifas_cancha(id_cancha):
    try:
        return jsonify(tarifas_service.eliminar_tarifas_cancha(id_cancha, _uid())), 200
    except ValueError as e:
        return error_json(str(e))
    except Exception as e:
        return error_json("Error al eliminar las tarifas.", str(e), 500)


@tarifas_bp.get("/admin/canchas/<int:id_cancha>/tarifas/historial")
@require_auth(roles=["administrador"])
def historial_tarifas(id_cancha):
    try:
        return jsonify(tarifas_service.listar_historial_tarifas(id_cancha)), 200
    except Exception as e:
        return error_json("Error interno al obtener el historial.", str(e), 500)
