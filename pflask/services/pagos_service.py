"""Modulo 4: Gestion de Pagos.

Cubre el documento: efectivo en caja, comprobantes QR/transferencia con
validacion real del archivo, saldo con anticipos, idempotencia, expiracion,
devoluciones solicitadas, arqueo y cierre de caja, recibo PDF y auditoria.
"""

import hashlib
import os
from datetime import date, datetime, timedelta
from decimal import Decimal

from flask import current_app
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from extensions import db
from models.pago import (
    ESTADO_APROBADO,
    ESTADO_DEVUELTO,
    ESTADO_EXPIRADO,
    ESTADO_PENDIENTE,
    ESTADO_PENDIENTE_VALIDACION,
    ESTADO_RECHAZADO,
    ESTADOS_PAGO,
    ESTADOS_TERMINALES_PAGO,
    ETIQUETA_ESTADO,
    METODOS_DIGITALES,
    METODOS_PAGO_VALIDOS,
    DevolucionSolicitud,
    Pago,
    PagoAuditoria,
    TurnoCaja,
)
from models.reserva import Reserva
from models.cancha import Cancha
from models.empleado import Empleado

#: El documento limita el comprobante a 5 MB.
MAX_COMPROBANTE_BYTES = 5 * 1024 * 1024

#: Firmas reales de los archivos admitidos (no se confia en la extension).
FIRMAS = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "application/pdf": (b"%PDF",),
}
EXTENSION_POR_TIPO = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "application/pdf": ".pdf",
}

#: Minutos que un comprobante puede esperar la validacion del empleado.
MINUTOS_VIGENCIA_COMPROBANTE = 60 * 24


# ============================================================
# SALDO
# ============================================================
def _neto_pagado(id_reserva):
    """Dinero que el cliente dejo en la reserva: pagado menos lo devuelto.

    Cuentan los pagos aprobados y los devueltos (un devuelto fue pagado y luego
    revertido), y se resta todo lo que salio por devoluciones. Asi una devolucion
    parcial vuelve a deber esa parte, y una total deja la reserva a deber el
    monto completo.

    Hace flush explicito porque el agregado se calcula con SQL crudo y debe
    ver los cambios de estado que aun no se enviaron a la base.
    """
    db.session.flush()
    fila = db.session.execute(
        text("""
            SELECT
                COALESCE(SUM(monto) FILTER (
                        WHERE estado_pago IN (:aprobado, :devuelto)), 0)
                - COALESCE(SUM(monto_devuelto) FILTER (
                        WHERE estado_pago IN (:aprobado, :devuelto)), 0)
            FROM pago
            WHERE id_reserva = :id_reserva
        """),
        {
            "aprobado": ESTADO_APROBADO,
            "devuelto": ESTADO_DEVUELTO,
            "id_reserva": id_reserva,
        },
    ).first()
    return round(float(fila[0] or 0), 2)


def saldo_reserva(id_reserva):
    """saldo = monto_total_reserva - pagos aprobados (anticipos parciales)."""
    reserva = db.session.get(Reserva, id_reserva)
    if not reserva:
        raise ValueError("La reserva indicada no existe.")
    total = float(reserva.monto_total or 0)
    return round(total - _neto_pagado(id_reserva), 2)


def _tiene_pago_en_curso(id_reserva):
    """True si hay un pago registrado que aun puede confirmarse.

    Un pago pendiente de validacion todavia no suma al saldo, pero el cliente
    ya actuo: no debe perder el horario mientras el empleado revisa el
    comprobante.
    """
    return Pago.query.filter(
        Pago.id_reserva == id_reserva,
        Pago.estado_pago.in_([ESTADO_PENDIENTE, ESTADO_PENDIENTE_VALIDACION,
                              ESTADO_APROBADO]),
    ).count() > 0


def _sincronizar_reserva(reserva):
    """Regla decidida: solo el saldo en 0 confirma la reserva.

    Mientras la reserva este pendiente, deja de caducar en cuanto existe un pago
    en curso (anticipo aprobado o comprobante por validar). Un pago rechazado o
    expirado no la protege, y el saldo sigue contando solo dinero aprobado.
    """
    if reserva.estado_reserva not in ("pendiente",):
        return reserva
    saldo = saldo_reserva(reserva.id_reserva)
    if saldo <= 0:
        reserva.estado_reserva = "confirmada"
        reserva.expira_en = None
        # Aviso al cliente de que su reserva quedo confirmada. Se encola sin
        # commit porque el flujo que nos llamo todavia esta transaccionando.
        # Al administrador no se le avisa aqui: la creacion de la reserva ya
        # le encolo su "nueva_reserva" y repetirlo seria duplicar el aviso.
        try:
            from services import notificaciones_service

            notificaciones_service.avisar_confirmacion(reserva, commit=False)
        except Exception as ex:  # noqa: BLE001 - un aviso nunca tumba un cobro
            print(f"[NOTIFICACION OMITIDA] {ex}")
    elif _tiene_pago_en_curso(reserva.id_reserva):
        reserva.expira_en = None
    return reserva


# ============================================================
# CAJA
# ============================================================
def _turno_abierto(id_empleado, fecha=None):
    fecha = fecha or date.today()
    return TurnoCaja.query.filter_by(
        id_empleado=id_empleado, fecha=fecha
    ).first()


def turno_abierto_del_empleado(id_empleado, fecha=None):
    """Turno de caja abierto hoy, o None si el empleado no abrió caja."""
    turno = _turno_abierto(id_empleado, fecha)
    if turno and turno.estado == "abierto":
        return turno
    return None


def _caja_cerrada(id_empleado, fecha=None):
    """Tras el cierre la caja no admite mas movimientos de efectivo."""
    turno = _turno_abierto(id_empleado, fecha)
    return bool(turno and turno.estado == "cerrado")


def abrir_turno(id_empleado, fecha=None):
    if not db.session.get(Empleado, id_empleado):
        raise ValueError("El empleado indicado no existe.")
    fecha = fecha or date.today()
    if _turno_abierto(id_empleado, fecha):
        raise ValueError("Ya existe un turno abierto para ese empleado en esa fecha.")
    turno = TurnoCaja(id_empleado=id_empleado, fecha=fecha, estado="abierto")
    db.session.add(turno)
    db.session.commit()
    return turno.to_dict()


def listar_turnos(fecha=None):
    query = TurnoCaja.query
    if fecha:
        query = query.filter(TurnoCaja.fecha == fecha)
    return [t.to_dict() for t in query.order_by(TurnoCaja.fecha.desc()).all()]


def turno_actual(id_empleado, fecha=None):
    turno = _turno_abierto(id_empleado, fecha)
    return turno.to_dict() if turno else None


def previsualizar_arqueo(id_turno):
    """Suma los pagos aprobados dentro de la ventana del turno.

    Un turno cerrado tambien se puede consultar: al cerrarlo se guardaron sus
    totales, y reabrir la vista no debe modificar nada.
    """
    turno = db.session.get(TurnoCaja, id_turno)
    if not turno:
        raise ValueError("El turno no existe.")

    inicio, fin = _ventana_turno(turno)
    pagos = Pago.query.filter(
        Pago.estado_pago == ESTADO_APROBADO,
        Pago.metodo_pago == "efectivo",
        Pago.id_empleado == turno.id_empleado,
        Pago.fecha_pago >= inicio,
        Pago.fecha_pago <= fin,
    ).all()

    esperado = round(sum(float(p.monto) for p in pagos), 2)
    fila = db.session.execute(
        text("""
            SELECT
                COALESCE(SUM(p.monto_devuelto), 0) AS total,
                COUNT(p.id_pago) AS cantidad
            FROM pago p
            WHERE p.id_empleado = :id_empleado
              AND p.metodo_pago = 'efectivo'
              AND p.fecha_pago BETWEEN :inicio AND :fin
              AND p.estado_pago = :devuelto
        """),
        {
            "id_empleado": turno.id_empleado,
            "inicio": inicio,
            "fin": fin,
            "devuelto": ESTADO_DEVUELTO,
        },
    ).first()
    total_devuelto = round(float(fila[0] or 0), 2)
    cantidad_devoluciones = int(fila[1] or 0)
    esperado = round(esperado - total_devuelto, 2)

    digitales = {m: 0.0 for m in METODOS_DIGITALES}
    for metodo in METODOS_DIGITALES:
        digitales[metodo] = round(
            float(
                db.session.execute(
                    text("""
                        SELECT COALESCE(SUM(p.monto), 0)
                        FROM pago p
                        WHERE p.id_empleado = :id_empleado
                          AND p.metodo_pago = :metodo
                          AND p.estado_pago = :aprobado
                          AND p.fecha_pago BETWEEN :inicio AND :fin
                    """),
                    {
                        "id_empleado": turno.id_empleado,
                        "metodo": metodo,
                        "aprobado": ESTADO_APROBADO,
                        "inicio": inicio,
                        "fin": fin,
                    },
                ).scalar()
                or 0
            ),
            2,
        )

    return {
        "id_turno": id_turno,
        "empleado": turno.id_empleado,
        "fecha": turno.fecha.isoformat(),
        "ventana": {
            "desde": inicio.isoformat(),
            "hasta": (fin or datetime.now()).isoformat(),
        },
        "monto_esperado_efectivo": esperado,
        "total_devuelto_efectivo": total_devuelto,
        "cantidad_devoluciones": cantidad_devoluciones,
        "total_qr": digitales.get("qr", 0.0),
        "total_transferencia": digitales.get("transferencia", 0.0),
        "total_tarjeta": digitales.get("tarjeta", 0.0),
        "total_digital": round(sum(digitales.values()), 2),
        "cantidad_pagos": len(pagos),
        "pagos": [p.to_dict() for p in pagos],
    }


def _ventana_turno(turno):
    """Del inicio del turno hasta su cierre (o hasta ahora si sigue abierto)."""
    if turno.hora_cierre is not None:
        return turno.hora_apertura, turno.hora_cierre
    # Turno abierto: cuenta todo lo del dia hasta el momento actual.
    inicio = datetime.combine(turno.fecha, datetime.min.time())
    return inicio, datetime.now()


def cerrar_turno(id_turno, monto_fisico, observaciones=None, id_usuario=None):
    turno = db.session.get(TurnoCaja, id_turno)
    if not turno:
        raise ValueError("El turno no existe.")
    if turno.estado == "cerrado":
        raise ValueError("El turno ya está cerrado.")

    try:
        fisico = float(monto_fisico)
    except (TypeError, ValueError):
        raise ValueError("Debe indicar el monto físico de la caja.")
    if fisico < 0:
        raise ValueError("El monto físico no puede ser negativo.")

    arqueo = previsualizar_arqueo(id_turno)
    esperado = arqueo["monto_esperado_efectivo"]
    diferencia = round(fisico - esperado, 2)
    if diferencia != 0 and not (observaciones or "").strip():
        raise ValueError(
            "Hay diferencia entre el efectivo contado y el esperado. "
            "Debes registrar una observación antes de cerrar la caja."
        )

    turno.monto_esperado_efectivo = esperado
    turno.monto_fisico = fisico
    turno.diferencia = diferencia
    turno.total_qr = arqueo["total_qr"]
    turno.total_transferencia = arqueo["total_transferencia"]
    turno.total_tarjeta = arqueo["total_tarjeta"]
    turno.cantidad_pagos = arqueo["cantidad_pagos"]
    turno.cantidad_devoluciones = arqueo["cantidad_devoluciones"]
    turno.observaciones = observaciones
    turno.estado = "cerrado"
    turno.hora_cierre = datetime.now()
    turno.id_usuario_cierre = id_usuario
    db.session.commit()
    return turno.to_dict()


# ============================================================
# COMPROBANTES
# ============================================================
def _detectar_tipo(primeros_bytes):
    """Valida el TIPO REAL del archivo, no la extension."""
    for tipo, firmas in FIRMAS.items():
        if all(primeros_bytes.startswith(f) for f in firmas):
            return tipo
    return None


def _guardar_comprobante(archivo, id_reserva, id_pago=None):
    """Valida, hashea y guarda el comprobante. Devuelve los metadatos."""
    if archivo is None or not getattr(archivo, "filename", ""):
        raise ValueError("Debes adjuntar el archivo del comprobante.")

    datos = archivo.read()
    if not datos:
        raise ValueError("El archivo del comprobante está vacío.")
    if len(datos) > MAX_COMPROBANTE_BYTES:
        raise ValueError("El comprobante no puede superar los 5 MB.")

    tipo = _detectar_tipo(datos[:8])
    if not tipo:
        raise ValueError(
            "El comprobante debe ser un JPG, PNG o PDF real. "
            "El tipo del archivo no coincide con un formato admitido."
        )

    sha = hashlib.sha256(datos).hexdigest()
    carpeta = os.path.join(current_app.config["UPLOAD_FOLDER"], "comprobantes")
    os.makedirs(carpeta, exist_ok=True)
    nombre = f"{id_reserva}_{sha[:16]}{EXTENSION_POR_TIPO[tipo]}"
    ruta = os.path.join(carpeta, nombre)
    with open(ruta, "wb") as f:
        f.write(datos)

    return {
        "ruta": nombre,
        "sha256": sha,
        "content_type": tipo,
        "tamano_bytes": len(datos),
        "nombre_original": archivo.filename,
    }


# ============================================================
# REGISTRO DE PAGOS
# ============================================================
def _validar_metodo(metodo):
    metodo = (metodo or "").strip().lower()
    if metodo not in METODOS_PAGO_VALIDOS:
        raise ValueError(
            "Método de pago no válido. Use: efectivo, qr, transferencia o tarjeta."
        )
    return metodo


def _pago_por_referencia(referencia):
    if not referencia:
        return None
    return Pago.query.filter_by(referencia=str(referencia).strip()).first()


def registrar_pago_efectivo(datos, id_usuario=None):
    """Efectivo: lo registra el empleado y queda APROBADO directo.

    El documento exige turno y empleado. Si no se indica el turno, se usa el
    que el empleado tenga abierto hoy.
    """
    id_empleado = datos.get("id_empleado")
    if id_empleado in (None, ""):
        raise ValueError("El efectivo requiere el empleado responsable.")
    if not db.session.get(Empleado, int(id_empleado)):
        raise ValueError("El empleado indicado no existe.")

    id_turno = datos.get("id_turno")
    if id_turno in (None, ""):
        turno = turno_abierto_del_empleado(int(id_empleado))
        if not turno:
            raise ValueError(
                "No tienes un turno de caja abierto. Abre tu turno antes de "
                "registrar pagos en efectivo."
            )
    else:
        turno = db.session.get(TurnoCaja, int(id_turno))
        if not turno:
            raise ValueError("El turno indicado no existe.")
        if turno.estado == "cerrado":
            raise ValueError("La caja de este turno está cerrada: no admite más movimientos.")
        if turno.id_empleado != int(id_empleado):
            raise ValueError("El turno no pertenece al empleado indicado.")

    return _crear_pago(
        datos,
        metodo="efectivo",
        estado=ESTADO_APROBADO,
        id_usuario=id_usuario,
        id_empleado=int(id_empleado),
    )


def registrar_comprobante(datos, archivo, id_usuario=None):
    """QR o transferencia.

    Sin archivo el pago queda 'pendiente': es la intencion de pago del cliente
    y el comprobante se puede adjuntar despues. Con archivo pasa directo a
    'pendiente_validacion', a la espera del empleado.
    """
    metodo = _validar_metodo(datos.get("metodo_pago"))
    if metodo == "efectivo":
        raise ValueError("El efectivo se registra en caja, no con comprobante.")
    if not (datos.get("referencia") or "").strip():
        raise ValueError("Indica la referencia de la operación (QR o transferencia).")

    estado = ESTADO_PENDIENTE_VALIDACION if archivo is not None else ESTADO_PENDIENTE
    return _crear_pago(
        datos,
        metodo=metodo,
        estado=estado,
        id_usuario=id_usuario,
        archivo=archivo,
    )


def adjuntar_comprobante(id_pago, archivo, id_usuario=None):
    """El cliente adjunta el comprobante a un pago que quedó pendiente."""
    pago = db.session.get(Pago, id_pago)
    if not pago:
        raise ValueError("El pago no existe.")
    if pago.metodo_pago == "efectivo":
        raise ValueError("El efectivo no lleva comprobante adjunto.")
    if pago.estado_pago != ESTADO_PENDIENTE:
        raise ValueError(
            f"Solo se adjunta comprobante a pagos pendientes (estado actual: "
            f"'{pago.estado_pago}')."
        )
    if not archivo:
        raise ValueError("Debes adjuntar el archivo del comprobante.")

    meta = _guardar_comprobante(archivo, pago.id_reserva)
    pago.comprobante = meta["ruta"]
    pago.sha256 = meta["sha256"]
    pago.content_type = meta["content_type"]
    pago.tamano_bytes = meta["tamano_bytes"]
    pago.nombre_original = meta["nombre_original"]
    pago.estado_pago = ESTADO_PENDIENTE_VALIDACION

    try:
        db.session.flush()
    except IntegrityError as e:
        db.session.rollback()
        orig = str(getattr(e, "orig", e))
        if "ux_pago_sha256" in orig:
            raise ValueError("Ese comprobante ya fue registrado en otro pago.")
        raise

    _historial_reserva(
        pago.id_reserva,
        "comprobante_adjunto",
        f"Comprobante adjunto al pago {pago.id_pago} "
        f"({meta['content_type']}, {meta['tamano_bytes']} bytes).",
        id_usuario,
    )
    db.session.commit()
    return {
        "mensaje": "Comprobante adjunto. Queda pendiente de validación.",
        "pago": pago.to_dict(),
        "saldo_reserva": saldo_reserva(pago.id_reserva),
    }


def _crear_pago(
    datos,
    metodo,
    estado,
    id_usuario=None,
    id_empleado=None,
    archivo=None,
):
    """Alta de un pago. El turno de caja no se guarda en el pago: se deduce
    del empleado y de la franja horaria del turno (ver _ventana_turno)."""
    id_reserva = datos.get("id_reserva")
    if id_reserva in (None, ""):
        raise ValueError("El pago debe indicar la reserva.")
    reserva = db.session.get(Reserva, int(id_reserva))
    if not reserva:
        raise ValueError("La reserva indicada no existe.")
    if reserva.estado_reserva in ("cancelada", "expirada", "completada"):
        raise ValueError(
            f"No se pueden registrar pagos en una reserva '{reserva.estado_reserva}'."
        )

    try:
        monto = round(float(datos.get("monto")), 2)
    except (TypeError, ValueError):
        raise ValueError("El monto del pago es obligatorio y debe ser numérico.")
    if monto <= 0:
        raise ValueError("El monto del pago debe ser mayor a 0.")

    # Idempotencia: misma referencia => mismo pago, no uno nuevo.
    referencia = (datos.get("referencia") or "").strip() or None
    if referencia:
        existente = _pago_por_referencia(referencia)
        if existente:
            return {
                "mensaje": "El pago ya fue registrado con esa referencia.",
                "pago": existente.to_dict(),
                "duplicado": True,
            }

    saldo = saldo_reserva(reserva.id_reserva)
    if saldo <= 0:
        raise ValueError("Esta reserva ya no tiene saldo pendiente por pagar.")
    if monto > saldo:
        raise ValueError(
            f"El monto supera el saldo pendiente de la reserva (Bs {saldo})."
        )

    meta = _guardar_comprobante(archivo, reserva.id_reserva) if archivo is not None else None

    pago = Pago(
        metodo_pago=metodo,
        estado_pago=estado,
        monto=monto,
        fecha_pago=datetime.now(),
        referencia=referencia,
        id_reserva=reserva.id_reserva,
        id_empleado=id_empleado if id_empleado is not None else datos.get("id_empleado"),
        id_usuario=id_usuario,
        id_usuario_validador=id_usuario if estado == ESTADO_APROBADO else None,
    )
    if meta:
        pago.comprobante = meta["ruta"]
        pago.sha256 = meta["sha256"]
        pago.content_type = meta["content_type"]
        pago.tamano_bytes = meta["tamano_bytes"]
        pago.nombre_original = meta["nombre_original"]
    db.session.add(pago)
    try:
        db.session.flush()
    except IntegrityError as e:
        db.session.rollback()
        orig = str(getattr(e, "orig", e))
        if "ux_pago_referencia" in orig or "ux_pago_sha256" in orig:
            raise ValueError("Esa referencia o comprobante ya fue registrado.")
        raise

    _sincronizar_reserva(reserva)
    _historial_reserva(
        reserva.id_reserva,
        "pago_registrado",
        f"Pago {metodo} Bs {monto} ({estado}). Saldo: Bs {saldo_reserva(reserva.id_reserva)}.",
        id_usuario,
    )
    db.session.commit()

    return {
        "mensaje": (
            "Pago en efectivo aprobado." if estado == ESTADO_APROBADO
            else "Comprobante recibido. Queda pendiente de validación."
        ),
        "pago": pago.to_dict(),
        "duplicado": False,
        "saldo_reserva": saldo_reserva(reserva.id_reserva),
        "estado_reserva": reserva.estado_reserva,
    }


def _historial_reserva(id_reserva, tipo, detalle, id_usuario=None):
    """Trazabilidad: el pago deja rastro en el historial de la reserva."""
    from models.historial_reserva import HistorialReserva

    fila = HistorialReserva(
        id_reserva=id_reserva,
        tipo_cambio=tipo,
        detalle=detalle,
        id_usuario=id_usuario,
        fecha=datetime.now(),
    )
    db.session.add(fila)


# ============================================================
# VALIDACION DEL COMPROBANTE
# ============================================================
def _empleado_de_usuario(id_usuario):
    if not id_usuario:
        return None
    return db.session.query(Empleado).filter_by(id_usuario=id_usuario).first()


def aprobar_pago(id_pago, id_usuario=None, observacion=None):
    pago = db.session.get(Pago, id_pago)
    if not pago:
        raise ValueError("El pago no existe.")
    if pago.estado_pago == ESTADO_APROBADO:
        raise ValueError("El pago ya está aprobado.")
    if pago.estado_pago != ESTADO_PENDIENTE_VALIDACION:
        raise ValueError(
            f"Solo se aprueban pagos pendientes de validación (estado actual: "
            f"'{pago.estado_pago}')."
        )
    if not pago.comprobante:
        raise ValueError("El pago no tiene comprobante adjunto.")

    pago.estado_pago = ESTADO_APROBADO
    pago.fecha_validacion = datetime.now()
    pago.id_usuario_validador = id_usuario
    # El empleado que valida es quien procesa el pago: sin esto el arqueo de
    # caja no podria imputar el cobro digital a ningun turno.
    if pago.id_empleado is None:
        empleado = _empleado_de_usuario(id_usuario)
        pago.id_empleado = empleado.id_empleado if empleado else None

    reserva = db.session.get(Reserva, pago.id_reserva)
    _sincronizar_reserva(reserva)
    saldo = saldo_reserva(pago.id_reserva)
    _historial_reserva(
        pago.id_reserva,
        "pago_aprobado",
        f"Pago {pago.id_pago} aprobado. Saldo: Bs {saldo}. "
        f"Reserva: {reserva.estado_reserva}."
        + (f" Observación: {observacion}" if observacion else ""),
        id_usuario,
    )
    db.session.commit()
    return {
        "mensaje": "Pago aprobado.",
        "pago": pago.to_dict(),
        "saldo_reserva": saldo,
        "estado_reserva": reserva.estado_reserva,
    }


def rechazar_pago(id_pago, motivo, id_usuario=None):
    """El rechazo SIEMPRE exige motivo."""
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValueError("El rechazo del pago requiere un motivo.")

    pago = db.session.get(Pago, id_pago)
    if not pago:
        raise ValueError("El pago no existe.")
    if pago.estado_pago != ESTADO_PENDIENTE_VALIDACION:
        raise ValueError(
            f"Solo se rechazan pagos pendientes de validación (estado actual: "
            f"'{pago.estado_pago}')."
        )

    pago.estado_pago = ESTADO_RECHAZADO
    pago.motivo_rechazo = motivo
    pago.fecha_validacion = datetime.now()
    pago.id_usuario_validador = id_usuario

    _historial_reserva(
        pago.id_reserva,
        "pago_rechazado",
        f"Pago {pago.id_pago} rechazado. Motivo: {motivo}.",
        id_usuario,
    )
    db.session.commit()
    return {
        "mensaje": "Pago rechazado.",
        "pago": pago.to_dict(),
        "saldo_reserva": saldo_reserva(pago.id_reserva),
    }


# ============================================================
# EXPIRACION
# ============================================================
def expirar_pagos_vencidos():
    """El pago no completado a tiempo expira y avisa a Reservas.

    El plazo corre desde ``Pago.fecha_pago`` y no desde ``Reserva.expira_en``:
    la reserva deja de caducar en cuanto el cliente registra un pago, asi que
    un comprobante que el empleado nunca valida tiene que vencer por su cuenta.
    """
    ahora = datetime.now()
    limite = ahora - timedelta(minutes=MINUTOS_VIGENCIA_COMPROBANTE)
    pagos = Pago.query.filter(
        Pago.estado_pago.in_([ESTADO_PENDIENTE, ESTADO_PENDIENTE_VALIDACION]),
        Pago.fecha_pago <= limite,
    ).all()

    expirados = []
    reservas_afectadas = set()
    for pago in pagos:
        pago.estado_pago = ESTADO_EXPIRADO
        pago.fecha_validacion = ahora
        expirados.append(pago.to_dict())
        reservas_afectadas.add(pago.id_reserva)

    for id_reserva in reservas_afectadas:
        _historial_reserva(
            id_reserva,
            "pago_expirado",
            "El comprobante venció sin ser validado por un empleado.",
            None,
        )
    if expirados:
        db.session.commit()

    # La reserva que se queda sin dinero posible también caduca, para que el
    # horario vuelva a estar disponible.
    reservas_expiradas = 0
    for id_reserva in reservas_afectadas:
        reserva = db.session.get(Reserva, id_reserva)
        if not reserva or reserva.estado_reserva != "pendiente":
            continue
        if saldo_reserva(id_reserva) <= 0 or _tiene_pago_en_curso(id_reserva):
            continue
        reserva.estado_reserva = "expirada"
        reserva.expira_en = None
        reserva.motivo_cancelacion = "Expirada por falta de pago (comprobante no validado)"
        _historial_reserva(
            id_reserva, "expiracion", "El comprobante venció y la reserva quedó sin pagos.",
            None,
        )
        reservas_expiradas += 1
    if reservas_expiradas:
        db.session.commit()

    # El flujo de Reservas cierra ademas las pendientes que vencieron por el
    # plazo original de 15 minutos.
    from services import reservas_service

    return {
        "expirados": len(expirados),
        "pagos": expirados,
        "reservas_expiradas": reservas_expiradas + reservas_service.expirar_reservas_vencidas(),
    }


# ============================================================
# DEVOLUCIONES
# ============================================================
def _preparar_solicitud_devolucion(id_pago, motivo, monto=None, current_user=None):
    """Valida y crea la solicitud de devolucion SIN commit.

    Se separa del endpoint para que otros flujos (por ejemplo la cancelacion
    de una reserva) puedan anadir la devolucion dentro de su propia transaccion
    y no quede un pago devuelto con la reserva todavia sin cancelar.
    """
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValueError("La solicitud de devolución requiere un motivo.")

    pago = db.session.get(Pago, id_pago)
    if not pago:
        raise ValueError("El pago no existe.")
    if pago.estado_pago != ESTADO_APROBADO:
        raise ValueError(
            f"Solo se pueden devolver pagos aprobados (estado actual: "
            f"'{pago.estado_pago}')."
        )
    if float(pago.monto_devuelto or 0) >= float(pago.monto):
        raise ValueError("Este pago ya fue devuelto por completo.")

    disponible = pago.saldo_restante
    try:
        solicitado = round(float(monto), 2) if monto not in (None, "") else disponible
    except (TypeError, ValueError):
        raise ValueError("El monto a devolver es inválido.")
    if solicitado <= 0:
        raise ValueError("El monto a devolver debe ser mayor a 0.")
    if solicitado > disponible:
        raise ValueError(
            f"No se puede devolver Bs {solicitado}: el pago solo tiene "
            f"Bs {disponible} por devolver."
        )

    pendiente = DevolucionSolicitud.query.filter_by(
        id_pago=id_pago, estado="solicitada"
    ).first()
    if pendiente:
        raise ValueError("Ya hay una solicitud de devolución pendiente para este pago.")

    cliente_id = None
    usuario_id = None
    if current_user is not None:
        usuario_id = getattr(current_user, "id_usuario", None)
        reserva = db.session.get(Reserva, pago.id_reserva)
        cliente_id = reserva.id_cliente if reserva else None

    solicitud = DevolucionSolicitud(
        id_pago=id_pago,
        id_cliente=cliente_id,
        id_usuario_solicitante=usuario_id,
        monto=solicitado,
        motivo=motivo,
        estado="solicitada",
    )
    db.session.add(solicitud)
    return solicitud


def solicitar_devolucion(id_pago, motivo, monto=None, current_user=None):
    """El cliente solicita la devolucion, solo sobre pagos aprobados."""
    solicitud = _preparar_solicitud_devolucion(id_pago, motivo, monto, current_user)
    pago = db.session.get(Pago, solicitud.id_pago)
    _historial_reserva(
        pago.id_reserva,
        "devolucion_solicitada",
        f"Devolución de Bs {solicitud.monto} solicitada sobre el pago {id_pago}. "
        f"Motivo: {solicitud.motivo}.",
        getattr(current_user, "id_usuario", None),
    )
    db.session.commit()
    return {
        "mensaje": "Solicitud de devolución registrada. Queda pendiente de revisión.",
        "solicitud": solicitud.to_dict(),
    }


def aprobar_devolucion(id_solicitud, id_usuario=None):
    """El empleado aprueba: se guarda monto devuelto y fecha."""
    solicitud = db.session.get(DevolucionSolicitud, id_solicitud)
    if not solicitud:
        raise ValueError("La solicitud no existe.")
    if solicitud.estado != "solicitada":
        raise ValueError(
            f"La solicitud ya fue resuelta (estado: '{solicitud.estado}')."
        )

    pago = db.session.get(Pago, solicitud.id_pago)
    if pago.estado_pago != ESTADO_APROBADO:
        raise ValueError("El pago ya no está aprobado: no se puede devolver.")
    if solicitud.monto > pago.saldo_restante:
        raise ValueError(
            f"El pago solo tiene Bs {pago.saldo_restante} por devolver."
        )

    pago.monto_devuelto = round(
        float(pago.monto_devuelto or 0) + float(solicitud.monto), 2
    )
    pago.fecha_devolucion = datetime.now()
    pago.motivo_devolucion = solicitud.motivo
    # Solo cuando se devuelve todo el pago pasa a Devuelto.
    if pago.saldo_restante <= 0:
        pago.estado_pago = ESTADO_DEVUELTO

    solicitud.estado = "aprobada"
    solicitud.id_usuario_decision = id_usuario
    solicitud.monto_devuelto = solicitud.monto
    solicitud.fecha_devolucion = pago.fecha_devolucion
    solicitud.fecha_decision = datetime.now()

    _historial_reserva(
        pago.id_reserva,
        "devolucion_aprobada",
        f"Devolución de Bs {solicitud.monto} aprobada sobre el pago {pago.id_pago}. "
        f"Estado del pago: {pago.estado_pago}.",
        id_usuario,
    )
    db.session.commit()
    return {
        "mensaje": "Devolución aprobada.",
        "solicitud": solicitud.to_dict(),
        "pago": pago.to_dict(),
        "saldo_reserva": saldo_reserva(pago.id_reserva),
    }


def rechazar_devolucion(id_solicitud, motivo, id_usuario=None):
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValueError("El rechazo de la devolución requiere un motivo.")

    solicitud = db.session.get(DevolucionSolicitud, id_solicitud)
    if not solicitud:
        raise ValueError("La solicitud no existe.")
    if solicitud.estado != "solicitada":
        raise ValueError(
            f"La solicitud ya fue resuelta (estado: '{solicitud.estado}')."
        )

    solicitud.estado = "rechazada"
    solicitud.motivo_decision = motivo
    solicitud.id_usuario_decision = id_usuario
    solicitud.fecha_decision = datetime.now()

    pago = db.session.get(Pago, solicitud.id_pago)
    _historial_reserva(
        pago.id_reserva,
        "devolucion_rechazada",
        f"Devolución rechazada. Motivo: {motivo}.",
        id_usuario,
    )
    db.session.commit()
    return {"mensaje": "Devolución rechazada.", "solicitud": solicitud.to_dict()}


def listar_devoluciones(estado=None, id_pago=None):
    query = DevolucionSolicitud.query
    if estado:
        query = query.filter_by(estado=estado)
    if id_pago:
        query = query.filter_by(id_pago=id_pago)
    filas = query.order_by(DevolucionSolicitud.id_solicitud.desc()).all()
    resultado = []
    for s in filas:
        datos = s.to_dict()
        pago = db.session.get(Pago, s.id_pago)
        if pago:
            datos["pago"] = pago.to_dict()
        resultado.append(datos)
    return resultado


# ============================================================
# AUDITORIA (administrador)
# ============================================================
def auditar_pago(id_pago, datos, id_usuario=None):
    """Compara el comprobante con el pago y deja la observacion."""
    pago = db.session.get(Pago, id_pago)
    if not pago:
        raise ValueError("El pago no existe.")

    monto = datos.get("monto_comprobante")
    fecha = datos.get("fecha_comprobante")
    metodo = (datos.get("metodo_comprobante") or "").strip().lower() or None
    referencia = (datos.get("referencia_comprobante") or "").strip() or None

    discrepancias = []
    if monto not in (None, ""):
        if abs(float(monto) - float(pago.monto)) > 0.009:
            discrepancias.append(
                f"El comprobante indica Bs {float(monto)} y el pago Bs {pago.monto}."
            )
    if fecha:
        try:
            f = datetime.strptime(str(fecha), "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("La fecha del comprobante debe tener formato YYYY-MM-DD.")
        if pago.fecha_pago and abs((pago.fecha_pago.date() - f).days) > 1:
            discrepancias.append(
                f"El comprobante indica {f.isoformat()} y el pago se registró el "
                f"{pago.fecha_pago.date().isoformat()}."
            )
    if metodo and metodo != pago.metodo_pago:
        discrepancias.append(
            f"El comprobante indica '{metodo}' y el pago '{pago.metodo_pago}'."
        )
    if referencia and pago.referencia and referencia != pago.referencia:
        discrepancias.append(
            f"La referencia del comprobante ({referencia}) no coincide con la del "
            f"pago ({pago.referencia})."
        )

    registro = PagoAuditoria(
        id_pago=id_pago,
        id_usuario=id_usuario,
        resultado="inconsistente" if discrepancias else "conforme",
        monto_comprobante=Decimal(str(monto)) if monto not in (None, "") else None,
        fecha_comprobante=(
            datetime.strptime(str(fecha), "%Y-%m-%d").date() if fecha else None
        ),
        metodo_comprobante=metodo,
        referencia_comprobante=referencia,
        observaciones=" ".join(discrepancias) or None,
    )
    db.session.add(registro)
    _historial_reserva(
        pago.id_reserva,
        "pago_auditado",
        f"Auditoría del pago {id_pago}: {registro.resultado}"
        + (f". {registro.observaciones}" if discrepancias else ""),
        id_usuario,
    )
    db.session.commit()
    return {
        "mensaje": (
            "El comprobante coincide con el pago."
            if not discrepancias
            else "Se detectaron inconsistencias en el comprobante."
        ),
        "auditoria": registro.to_dict(),
    }


def listar_auditorias(id_pago=None):
    query = PagoAuditoria.query
    if id_pago:
        query = query.filter_by(id_pago=id_pago)
    return [
        a.to_dict()
        for a in query.order_by(PagoAuditoria.id_auditoria.desc()).all()
    ]


# ============================================================
# LECTURA
# ============================================================
def listar_pagos(estado=None, con_detalle=False, id_cliente=None, id_reserva=None):
    if estado and estado not in ESTADOS_PAGO:
        raise ValueError(
            "Estado no válido. Use: " + ", ".join(ESTADOS_PAGO) + "."
        )

    query = Pago.query
    if estado:
        query = query.filter_by(estado_pago=estado)
    if id_reserva:
        query = query.filter_by(id_reserva=id_reserva)
    if id_cliente:
        query = query.join(Reserva).filter(Reserva.id_cliente == id_cliente)

    pagos = query.order_by(Pago.fecha_pago.desc()).all()
    if con_detalle:
        return [pago_detalle(p) for p in pagos]
    return [p.to_dict() for p in pagos]


def pago_detalle(pago):
    datos = pago.to_dict()
    datos["metodo_pago"] = (pago.metodo_pago or "").capitalize()
    reserva = db.session.get(Reserva, pago.id_reserva)
    if reserva:
        cancha = db.session.get(Cancha, reserva.id_cancha) if reserva.id_cancha else None
        datos["reserva"] = {
            "id_reserva": reserva.id_reserva,
            "fecha_reserva": reserva.fecha_reserva.isoformat() if reserva.fecha_reserva else None,
            "hora_inicio": reserva.hora_inicio.strftime("%H:%M") if reserva.hora_inicio else None,
            "estado_reserva": reserva.estado_reserva,
            "monto_total": float(reserva.monto_total or 0),
            "cancha": getattr(cancha, "nombre_cancha", None) if cancha else None,
            "cliente": _info_cliente_nombre(reserva.id_cliente),
        }
        datos["saldo_reserva"] = saldo_reserva(reserva.id_reserva)
    datos["solicitudes_devolucion"] = [
        s.to_dict()
        for s in DevolucionSolicitud.query.filter_by(id_pago=pago.id_pago).all()
    ]
    return datos


def obtener_pago_por_id(id_pago, con_detalle=True):
    pago = db.session.get(Pago, id_pago)
    if not pago:
        raise ValueError("El pago no existe.")
    return pago_detalle(pago) if con_detalle else pago


def _info_cliente_nombre(id_cliente):
    if not id_cliente:
        return None
    sql = text("""
        SELECT per.nombre || ' ' || per.apellido AS nombre
        FROM cliente cl
        JOIN usuario u   ON u.id_usuario = cl.id_usuario
        JOIN persona per ON per.id_persona = u.id_persona
        WHERE cl.id_cliente = :id_cliente
    """)
    fila = db.session.execute(sql, {"id_cliente": id_cliente}).first()
    return fila[0] if fila else None


def listar_reservas_para_pago():
    """Reservas sobre las que todavia tiene sentido cobrar.

    Solo entran las que NO estan pagadas y NO han terminado:
      - queda saldo por cobrar (saldo_reserva > 0),
      - el horario sigue vigente: fecha + hora_fin >= ahora,
      - el estado no es terminal (cancelada, expirada, completada).

    Se ordena de la mas proxima a la mas lejana: es la que se cobra primero.
    """
    sql = text("""
        SELECT
            r.id_reserva,
            r.fecha_reserva,
            r.hora_inicio,
            r.hora_fin,
            r.monto_total,
            r.estado_reserva,
            c.nombre_cancha,
            c.tipo_deporte,
            per.nombre || ' ' || per.apellido AS cliente
        FROM reserva r
        JOIN cancha c       ON c.id_cancha = r.id_cancha
        JOIN cliente cl     ON cl.id_cliente = r.id_cliente
        JOIN usuario u      ON u.id_usuario = cl.id_usuario
        JOIN persona per    ON per.id_persona = u.id_persona
        WHERE r.estado_reserva IN ('confirmada', 'pendiente')
          AND (r.fecha_reserva + r.hora_fin) >= NOW()
        ORDER BY r.fecha_reserva ASC, r.hora_inicio ASC
    """)
    filas = db.session.execute(sql).mappings().all()
    resultado = []
    for f in filas:
        saldo = saldo_reserva(f["id_reserva"])
        # Ya cubierta por pagos: no se ofrece para cobrar de nuevo.
        if saldo <= 0:
            continue
        item = {
            "id_reserva": f["id_reserva"],
            "fecha_reserva": str(f["fecha_reserva"]) if f["fecha_reserva"] else None,
            "hora_inicio": str(f["hora_inicio"]) if f["hora_inicio"] else None,
            "monto_total": float(f["monto_total"]) if f["monto_total"] is not None else None,
            "saldo_pendiente": saldo,
            "estado_reserva": f["estado_reserva"],
            "cancha": f["nombre_cancha"],
            "tipo_deporte": f["tipo_deporte"],
            "cliente": f["cliente"],
        }
        resultado.append(item)
    return resultado


# ============================================================
# RECIBO PDF
# ============================================================
def generar_recibo(id_pago):
    """Recibo solo para pagos aprobados o devueltos."""
    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    pago = db.session.get(Pago, id_pago)
    if not pago:
        raise ValueError("El pago no existe.")
    if pago.estado_pago not in (ESTADO_APROBADO, ESTADO_DEVUELTO):
        raise ValueError(
            "Solo se puede emitir el recibo de pagos aprobados o devueltos."
        )

    reserva = db.session.get(Reserva, pago.id_reserva)
    cancha = db.session.get(Cancha, reserva.id_cancha) if reserva else None
    cliente = _info_cliente_nombre(reserva.id_cliente) if reserva else None

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
    )
    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle("titulo", parent=estilos["Title"], fontSize=16, spaceAfter=4)
    normal = estilos["Normal"]

    elementos = [
        Paragraph("Comprobante de pago", titulo),
        Paragraph("Complejo Deportivo Canchas", estilos["Heading3"]),
        Spacer(1, 0.6 * cm),
    ]

    filas = [
        ["Recibo N°", str(pago.id_pago)],
        ["Referencia", pago.referencia or "-"],
        ["Fecha del pago", pago.fecha_pago.strftime("%d/%m/%Y %H:%M") if pago.fecha_pago else "-"],
        ["Estado", ETIQUETA_ESTADO.get(pago.estado_pago, pago.estado_pago)],
        ["Cliente", cliente or "-"],
        ["Cancha", getattr(cancha, "nombre_cancha", "-")],
        [
            "Reserva",
            f"#{pago.id_reserva} - {reserva.fecha_reserva.strftime('%d/%m/%Y')} "
            f"{reserva.hora_inicio.strftime('%H:%M') if reserva.hora_inicio else ''}"
            if reserva else "-",
        ],
        ["Método", (pago.metodo_pago or "").upper()],
        ["Monto pagado", f"Bs {float(pago.monto):.2f}"],
    ]
    if float(pago.monto_devuelto or 0) > 0:
        filas.append(["Monto devuelto", f"Bs {float(pago.monto_devuelto):.2f}"])

    tabla = Table(filas, colWidths=[5 * cm, 11 * cm])
    tabla.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elementos.append(tabla)
    elementos.append(Spacer(1, 0.8 * cm))
    elementos.append(Paragraph(
        "Documento generado automáticamente. No requiere firma.", normal
    ))

    doc.build(elementos)
    buffer.seek(0)
    return buffer, f"recibo-pago-{pago.id_pago}.pdf"
