from flask import Blueprint, jsonify, request
from extensions import db
from services.eventos_service import EventosService, TIPOS_EVENTO_VALIDOS, TIPO_EVENTO_PUBLICO
from validators.evento_validator import EventoValidator

# Integración con el sistema de autenticación y roles
try:
    from services.auth_service import require_auth, usuario_opcional
except ImportError:
    # Fallback transparente para desarrollo aislado si auth no está en la misma ruta
    def require_auth(roles=None):
        def decorator(fn):
            return fn
        return decorator

    def usuario_opcional():
        return None

eventos_bp = Blueprint("eventos", __name__, url_prefix="/api/eventos")


def _usuario_actual():
    """None = petición anónima (no vino Authorization: Bearer)."""
    return usuario_opcional()


@eventos_bp.route("", methods=["GET"])
def get_eventos():
    """Listado de eventos. Soporta filtro opcional ?tipo=..."""
    try:
        tipo = request.args.get("tipo")
        eventos = EventosService.get_all_eventos(tipo=tipo)
        return jsonify([e.to_dict() for e in eventos]), 200
    except Exception as ex:
        return jsonify({"error": "Error al consultar los eventos", "detalle": str(ex)}), 500


@eventos_bp.route("/tipos", methods=["GET"])
def get_tipos():
    """Catálogo de tipos de evento permitidos."""
    return jsonify([{"valor": t, "etiqueta": t} for t in TIPOS_EVENTO_VALIDOS]), 200


@eventos_bp.route("/disponibilidad", methods=["GET"])
def check_disponibilidad():
    try:
        ids_canchas = request.args.get("ids_canchas") or request.args.get("id_cancha")
        fecha = request.args.get("fecha_evento") or request.args.get("fecha")
        hora_inicio = request.args.get("hora_inicio")
        hora_fin = request.args.get("hora_fin")
        excluir_id = request.args.get("excluir_id")

        if not all([ids_canchas, fecha, hora_inicio, hora_fin]):
            return jsonify({
                "disponible": False,
                "motivo": "Faltan parámetros requeridos (ids_canchas/id_cancha, fecha_evento, hora_inicio, hora_fin).",
            }), 400

        resultado = EventosService.verificar_disponibilidad_cancha(
            ids_canchas=ids_canchas,
            fecha_str=fecha,
            hora_inicio_str=hora_inicio,
            hora_fin_str=hora_fin,
            id_evento_excluir=excluir_id,
        )
        return jsonify(resultado), 200
    except Exception as ex:
        return jsonify({"error": "Error al verificar disponibilidad", "detalle": str(ex)}), 500


@eventos_bp.route("/agenda-disponibilidad", methods=["GET"])
def get_agenda_disponibilidad():
    try:
        ids_canchas = request.args.get("ids_canchas") or request.args.get("id_cancha")
        fecha = request.args.get("fecha_evento") or request.args.get("fecha")
        mes = request.args.get("mes")
        excluir_id = request.args.get("excluir_id")

        if not ids_canchas or not fecha:
            return jsonify({
                "error": "Faltan parámetros requeridos (ids_canchas y fecha)."
            }), 400

        agenda = EventosService.obtener_agenda_ocupacion(
            ids_canchas=ids_canchas,
            fecha_str=fecha,
            mes_str=mes,
            id_evento_excluir=excluir_id,
        )
        return jsonify(agenda), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as ex:
        return jsonify({"error": "Error al obtener la agenda de disponibilidad", "detalle": str(ex)}), 500


@eventos_bp.route("/<int:id_evento>", methods=["GET"])
def get_evento(id_evento):
    try:
        evento = EventosService.get_evento_by_id(id_evento)
        if not evento:
            return jsonify({"error": "Evento no encontrado"}), 404
        return jsonify(evento.to_dict()), 200
    except Exception as ex:
        return jsonify({"error": "Error al consultar el evento", "detalle": str(ex)}), 500


@eventos_bp.route("", methods=["POST"])
@require_auth(roles=["administrador", "empleado"])
def create_evento():
    try:
        data = request.get_json()
        valido, errores = EventoValidator.validate_create_payload(data)
        if not valido:
            return jsonify({"error": "Datos inválidos", "detalles": errores}), 400

        nuevo = EventosService.create_evento(data)
        return jsonify(nuevo.to_dict()), 201
    except ValueError as ve:
        db.session.rollback()
        return jsonify({"error": str(ve)}), 400
    except Exception as ex:
        db.session.rollback()
        return jsonify({"error": "Error interno al crear el evento", "detalle": str(ex)}), 500


@eventos_bp.route("/<int:id_evento>", methods=["PUT"])
@require_auth(roles=["administrador", "empleado"])
def update_evento(id_evento):
    try:
        data = request.get_json()
        valido, errores = EventoValidator.validate_update_payload(data)
        if not valido:
            return jsonify({"error": "Datos inválidos", "detalles": errores}), 400

        evento_actualizado = EventosService.update_evento(id_evento, data)
        if not evento_actualizado:
            return jsonify({"error": "Evento no encontrado"}), 404
        return jsonify(evento_actualizado.to_dict()), 200
    except ValueError as ve:
        db.session.rollback()
        return jsonify({"error": str(ve)}), 400
    except Exception as ex:
        db.session.rollback()
        return jsonify({"error": "Error al actualizar el evento", "detalle": str(ex)}), 500


@eventos_bp.route("/<int:id_evento>", methods=["DELETE"])
@require_auth(roles=["administrador", "empleado"])
def delete_evento(id_evento):
    try:
        eliminado = EventosService.delete_evento(id_evento)
        if not eliminado:
            return jsonify({"error": "Evento no encontrado"}), 404
        return jsonify({"mensaje": "Evento eliminado exitosamente"}), 200
    except Exception as ex:
        db.session.rollback()
        return jsonify({"error": "Error al eliminar el evento", "detalle": str(ex)}), 500
