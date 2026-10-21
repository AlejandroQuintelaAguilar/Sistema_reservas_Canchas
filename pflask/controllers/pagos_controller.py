import os

from flask import Blueprint, current_app, g, jsonify, request, send_file
from sqlalchemy.exc import IntegrityError

from extensions import db
from models.pago import ESTADOS_PAGO, ETIQUETA_ESTADO
from models.reserva import Reserva
from services import pagos_service
from services.auth_service import require_auth
from utils.responses import error_json

pagos_bp = Blueprint("pagos", __name__, url_prefix="/api/pagos")
caja_bp = Blueprint("caja", __name__, url_prefix="/api/caja")

ROLES_OPERACION = ["administrador", "empleado"]


def _uid():
    return getattr(g, "current_user", None).id_usuario


def _json():
    return request.get_json(silent=True) or {}


def _es_dueno_del_pago(pago):
    """El cliente solo accede a los pagos de sus propias reservas.

    Acepta el modelo o el dict de ``pago_detalle`` segun como lo devuelva el
    servicio.
    """
    usuario = getattr(g, "current_user", None)
    if not usuario or not pago:
        return False
    from models.cliente import Cliente

    id_reserva = pago.get("id_reserva") if isinstance(pago, dict) else pago.id_reserva
    cliente = Cliente.query.filter_by(id_usuario=usuario.id_usuario).first()
    if not cliente:
        return False
    reserva = db.session.get(Reserva, id_reserva)
    return bool(reserva and reserva.id_cliente == cliente.id_cliente)


# ============================================================
# CONSULTA
# ============================================================
@pagos_bp.get("")
@require_auth()
def obtener_pagos():
    try:
        rol = getattr(g, "current_user", None).rol
        estado = request.args.get("estado")
        con_detalle = request.args.get("detalle", "0") in ("1", "true", "True")
        id_reserva = request.args.get("id_reserva")
        id_cliente = request.args.get("id_cliente")

        pagos = pagos_service.listar_pagos(
            estado,
            con_detalle=con_detalle,
            id_cliente=id_cliente,
            id_reserva=id_reserva,
        )

        # Un cliente solo ve los pagos de sus reservas.
        if rol == "cliente":
            visibles = []
            for pago in pagos:
                if _es_dueno_del_pago(pago):
                    visibles.append(pago)
            pagos = visibles

        return jsonify(pagos), 200
    except ValueError as e:
        return error_json(str(e))
    except Exception as e:
        return error_json("Error interno al obtener pagos.", str(e), 500)


@pagos_bp.get("/estados")
@require_auth()
def estados_pago():
    return jsonify({
        "estados": [
            {"valor": e, "etiqueta": ETIQUETA_ESTADO[e]} for e in ESTADOS_PAGO
        ]
    }), 200


@pagos_bp.get("/reservas-para-pago")
@require_auth(roles=ROLES_OPERACION)
def obtener_reservas_para_pago():
    try:
        return jsonify(pagos_service.listar_reservas_para_pago()), 200
    except Exception as e:
        return error_json("Error interno al obtener reservas.", str(e), 500)


@pagos_bp.get("/saldo/<int:id_reserva>")
@require_auth()
def saldo_de_reserva(id_reserva):
    try:
        return jsonify({
            "id_reserva": id_reserva,
            "saldo": pagos_service.saldo_reserva(id_reserva),
        }), 200
    except ValueError as e:
        return error_json(str(e), codigo=404)
    except Exception as e:
        return error_json("Error interno al obtener el saldo.", str(e), 500)


@pagos_bp.get("/<int:id_pago>")
@require_auth()
def obtener_pago(id_pago):
    if id_pago <= 0:
        return error_json("El id_pago debe ser mayor que 0.")
    try:
        pago = pagos_service.obtener_pago_por_id(id_pago)
        if getattr(g, "current_user", None).rol == "cliente" and not _es_dueno_del_pago(pago):
            return error_json("No tienes permiso para ver este pago.", codigo=403)
        return jsonify(pago), 200
    except ValueError as e:
        return error_json(str(e), codigo=404)
    except Exception as e:
        return error_json("Error interno al obtener el pago.", str(e), 500)


@pagos_bp.get("/<int:id_pago>/recibo")
@require_auth()
def recibo_pago(id_pago):
    try:
        pago = pagos_service.obtener_pago_por_id(id_pago, con_detalle=False)
        if getattr(g, "current_user", None).rol == "cliente" and not _es_dueno_del_pago(pago):
            return error_json("No tienes permiso para ver este recibo.", codigo=403)
        buffer, nombre = pagos_service.generar_recibo(id_pago)
        return send_file(
            buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=nombre,
        )
    except ValueError as e:
        return error_json(str(e))
    except Exception as e:
        return error_json("Error interno al generar el recibo.", str(e), 500)


@pagos_bp.get("/<int:id_pago>/comprobante")
@require_auth()
def ver_comprobante(id_pago):
    try:
        pago = pagos_service.obtener_pago_por_id(id_pago, con_detalle=False)
        if getattr(g, "current_user", None).rol == "cliente" and not _es_dueno_del_pago(pago):
            return error_json("No tienes permiso para ver este comprobante.", codigo=403)
        if not pago.comprobante:
            return error_json("Este pago no tiene comprobante adjunto.", codigo=404)
        carpeta = os.path.join(current_app.config["UPLOAD_FOLDER"], "comprobantes")
        ruta = os.path.join(carpeta, os.path.basename(pago.comprobante))
        if not os.path.exists(ruta):
            return error_json("El archivo del comprobante no existe.", codigo=404)
        return send_file(ruta, mimetype=pago.content_type or "application/octet-stream")
    except ValueError as e:
        return error_json(str(e), codigo=404)
    except Exception as e:
        return error_json("Error interno al obtener el comprobante.", str(e), 500)


# ============================================================
# REGISTRO
# ============================================================
@pagos_bp.post("")
@require_auth()
def crear_pago():
    """Efectivo: solo empleado/admin y con turno abierto. Digital: con comprobante."""
    data = _json()
    try:
        metodo = (data.get("metodo_pago") or "").strip().lower()
        if metodo == "efectivo":
            rol = getattr(g, "current_user", None).rol
            if rol not in ROLES_OPERACION:
                return error_json("Solo el personal registra pagos en efectivo.", codigo=403)
            # El efectivo queda a nombre del cajero. Un empleado nunca registra
            # en nombre de otro; el administrador si debe indicar a quien.
            if rol == "administrador":
                id_empleado = data.get("id_empleado")
                if id_empleado in (None, ""):
                    return error_json(
                        "Indica el empleado que recibe el efectivo."
                    )
            else:
                id_empleado = _empleado_del_usuario()
            data["id_empleado"] = id_empleado
            return jsonify(pagos_service.registrar_pago_efectivo(data, _uid())), 201

        if not data.get("id_reserva"):
            return error_json("El pago debe indicar la reserva.")
        return jsonify(
            pagos_service.registrar_comprobante(data, None, _uid())
        ), 201
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e))
    except IntegrityError as e:
        db.session.rollback()
        return error_json("No se pudo registrar el pago.", str(e.orig), 409)
    except Exception as e:
        db.session.rollback()
        return error_json("Error interno al registrar el pago.", str(e), 500)


@pagos_bp.post("/comprobante")
@require_auth()
def subir_comprobante():
    """El cliente adjunta el JPG/PNG/PDF del QR o la transferencia."""
    try:
        data = _json()
        data.update(request.form.to_dict())
        archivo = request.files.get("comprobante")
        return jsonify(pagos_service.registrar_comprobante(data, archivo, _uid())), 201
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e))
    except IntegrityError as e:
        db.session.rollback()
        return error_json("No se pudo registrar el comprobante.", str(e.orig), 409)
    except Exception as e:
        db.session.rollback()
        return error_json("Error interno al registrar el comprobante.", str(e), 500)


@pagos_bp.post("/<int:id_pago>/comprobante")
@require_auth()
def adjuntar_comprobante(id_pago):
    """El cliente adjunta despues el comprobante de un pago ya creado."""
    try:
        archivo = request.files.get("comprobante")
        return jsonify(
            pagos_service.adjuntar_comprobante(id_pago, archivo, _uid())
        ), 201
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e))
    except IntegrityError as e:
        db.session.rollback()
        return error_json("No se pudo adjuntar el comprobante.", str(e.orig), 409)
    except Exception as e:
        db.session.rollback()
        return error_json("Error interno al adjuntar el comprobante.", str(e), 500)


# ============================================================
# VALIDACION (empleado / administrador)
# ============================================================
@pagos_bp.post("/<int:id_pago>/aprobar")
@require_auth(roles=ROLES_OPERACION)
def aprobar_pago(id_pago):
    try:
        return jsonify(
            pagos_service.aprobar_pago(id_pago, _uid(), _json().get("observacion"))
        ), 200
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e))
    except Exception as e:
        db.session.rollback()
        return error_json("Error interno al aprobar el pago.", str(e), 500)


@pagos_bp.post("/<int:id_pago>/rechazar")
@require_auth(roles=ROLES_OPERACION)
def rechazar_pago(id_pago):
    try:
        return jsonify(pagos_service.rechazar_pago(id_pago, _json().get("motivo"), _uid())), 200
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e))
    except Exception as e:
        db.session.rollback()
        return error_json("Error interno al rechazar el pago.", str(e), 500)


# ============================================================
# DEVOLUCIONES
# ============================================================
@pagos_bp.post("/<int:id_pago>/devolucion")
@require_auth()
def solicitar_devolucion(id_pago):
    try:
        data = _json()
        return jsonify(
            pagos_service.solicitar_devolucion(
                id_pago,
                data.get("motivo"),
                data.get("monto"),
                getattr(g, "current_user", None),
            )
        ), 201
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e))
    except Exception as e:
        db.session.rollback()
        return error_json("Error interno al solicitar la devolución.", str(e), 500)


@pagos_bp.get("/devoluciones")
@require_auth()
def listar_devoluciones():
    try:
        return jsonify(
            pagos_service.listar_devoluciones(
                request.args.get("estado"), request.args.get("id_pago")
            )
        ), 200
    except Exception as e:
        return error_json("Error interno al obtener devoluciones.", str(e), 500)


@pagos_bp.post("/devoluciones/<int:id_solicitud>/aprobar")
@require_auth(roles=ROLES_OPERACION)
def aprobar_devolucion(id_solicitud):
    try:
        return jsonify(pagos_service.aprobar_devolucion(id_solicitud, _uid())), 200
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e))
    except Exception as e:
        db.session.rollback()
        return error_json("Error interno al aprobar la devolución.", str(e), 500)


@pagos_bp.post("/devoluciones/<int:id_solicitud>/rechazar")
@require_auth(roles=ROLES_OPERACION)
def rechazar_devolucion(id_solicitud):
    try:
        return jsonify(
            pagos_service.rechazar_devolucion(
                id_solicitud, _json().get("motivo"), _uid()
            )
        ), 200
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e))
    except Exception as e:
        db.session.rollback()
        return error_json("Error interno al rechazar la devolución.", str(e), 500)


# ============================================================
# CAJA Y ARQUEO
# ============================================================
@caja_bp.post("/turnos")
@require_auth(roles=ROLES_OPERACION)
def abrir_turno():
    try:
        data = _json()
        id_empleado = data.get("id_empleado")
        if id_empleado in (None, ""):
            id_empleado = _empleado_del_usuario()
        return jsonify(pagos_service.abrir_turno(int(id_empleado))), 201
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e))
    except Exception as e:
        db.session.rollback()
        return error_json("Error interno al abrir el turno.", str(e), 500)


@caja_bp.get("/turnos")
@require_auth(roles=ROLES_OPERACION)
def listar_turnos():
    try:
        return jsonify(pagos_service.listar_turnos(request.args.get("fecha"))), 200
    except Exception as e:
        return error_json("Error interno al obtener los turnos.", str(e), 500)


@caja_bp.get("/actual")
@require_auth(roles=ROLES_OPERACION)
def turno_actual():
    try:
        return jsonify(
            pagos_service.turno_actual(_empleado_del_usuario()) or {}
        ), 200
    except ValueError as e:
        # El administrador no siempre es empleado: no es un fallo del servidor.
        return error_json(str(e), codigo=400)
    except Exception as e:
        return error_json("Error interno al obtener el turno.", str(e), 500)


@caja_bp.get("/turnos/<int:id_turno>/arqueo")
@require_auth(roles=ROLES_OPERACION)
def arqueo_turno(id_turno):
    try:
        return jsonify(pagos_service.previsualizar_arqueo(id_turno)), 200
    except ValueError as e:
        return error_json(str(e))
    except Exception as e:
        return error_json("Error interno al calcular el arqueo.", str(e), 500)


@caja_bp.post("/turnos/<int:id_turno>/cerrar")
@require_auth(roles=ROLES_OPERACION)
def cerrar_turno(id_turno):
    try:
        data = _json()
        return jsonify(
            pagos_service.cerrar_turno(
                id_turno,
                data.get("monto_fisico"),
                data.get("observaciones"),
                _uid(),
            )
        ), 200
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e))
    except Exception as e:
        db.session.rollback()
        return error_json("Error interno al cerrar la caja.", str(e), 500)


# ============================================================
# AUDITORIA (administrador)
# ============================================================
@pagos_bp.post("/<int:id_pago>/auditar")
@require_auth(roles=["administrador"])
def auditar_pago(id_pago):
    try:
        return jsonify(pagos_service.auditar_pago(id_pago, _json(), _uid())), 201
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e))
    except Exception as e:
        db.session.rollback()
        return error_json("Error interno al auditar el pago.", str(e), 500)


@pagos_bp.get("/auditorias/listado")
@require_auth(roles=["administrador"])
def listar_auditorias():
    try:
        return jsonify(
            pagos_service.listar_auditorias(request.args.get("id_pago"))
        ), 200
    except Exception as e:
        return error_json("Error interno al obtener las auditorías.", str(e), 500)


def _empleado_del_usuario():
    """El usuario logueado que ademas es empleado registra su propia caja."""
    from models.empleado import Empleado

    usuario = getattr(g, "current_user", None)
    empleado = Empleado.query.filter_by(id_usuario=usuario.id_usuario).first()
    if not empleado:
        raise ValueError("Tu usuario no está registrado como empleado.")
    return empleado.id_empleado
