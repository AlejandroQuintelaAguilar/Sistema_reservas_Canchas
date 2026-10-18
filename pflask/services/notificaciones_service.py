"""Notificaciones automaticas.

Flujo del documento de requisitos:
    elegir plantilla -> guardar como PENDIENTE -> enviar por el canal
    (email, push o SMS) -> ENVIADO.
    Si falla -> FALLIDO, se registra el error y se reintenta con limite de
    intentos. Todo queda en el historial con fecha y destinatario.
    El envio es asincrono para no bloquear la reserva y los recordatorios son
    idempotentes, para no mandar el mismo aviso dos veces.
"""
import os
import re
import smtplib
from datetime import datetime, date, timedelta
from email.message import EmailMessage

from sqlalchemy.exc import IntegrityError

from extensions import db
from models.notificacion import (
    Notificacion,
    NotificacionIntento,
    ESTADOS_NOTIFICACION,
    MAX_INTENTOS_POR_DEFECTO,
)
from models.plantilla_notificacion import PlantillaNotificacion, CANALES
from models.reserva import Reserva
from models.cliente import Cliente
from models.persona import Persona
from models.usuario import Usuario
from models.cancha import Cancha

NOMBRE_COMPLEJO = os.getenv("NOMBRE_COMPLEJO", "Complejo Deportivo")
PLANTILLA_RECORDATORIO = "RECORDATORIO_RESERVA"
PLANTILLA_POR_TIPO = {
    "reserva_confirmada": "RESERVA_CONFIRMADA",
    "reserva_modificada": "RESERVA_MODIFICADA",
    "reserva_cancelada": "RESERVA_CANCELADA",
    "recordatorio_reserva": "RECORDATORIO_RESERVA",
    "nueva_reserva": "NUEVA_RESERVA",
    "nueva_cancelacion": "NUEVA_CANCELACION",
    "nueva_modificacion": "NUEVA_MODIFICACION",
}


# =====================================================================
# PLANTILLAS
# =====================================================================
def listar_plantillas(tipo=None, canal=None, incluir_inactivas=False):
    consulta = PlantillaNotificacion.query
    if tipo:
        consulta = consulta.filter(PlantillaNotificacion.tipo_evento == tipo)
    if canal:
        consulta = consulta.filter(PlantillaNotificacion.canal == canal)
    if not incluir_inactivas:
        consulta = consulta.filter(PlantillaNotificacion.activa.is_(True))
    return consulta.order_by(PlantillaNotificacion.nombre.asc()).all()


def obtener_plantilla(id_plantilla):
    plantilla = db.session.get(PlantillaNotificacion, id_plantilla)
    if not plantilla:
        raise ValueError("La plantilla no existe.")
    return plantilla


def obtener_plantilla_por_codigo(codigo):
    plantilla = PlantillaNotificacion.query.filter_by(codigo=codigo).first()
    if not plantilla:
        raise ValueError(f"La plantilla '{codigo}' no existe.")
    return plantilla


def crear_plantilla(data, id_administrador=None):
    codigo = (data.get("codigo") or "").strip().upper()
    if not codigo:
        raise ValueError("El campo 'codigo' es obligatorio.")
    if PlantillaNotificacion.query.filter_by(codigo=codigo).first():
        raise ValueError(f"Ya existe una plantilla con el código '{codigo}'.")

    tipo = data.get("tipo_evento")
    if tipo not in PLANTILLA_POR_TIPO:
        raise ValueError(
            f"'tipo_evento' no válido. Use: {', '.join(PLANTILLA_POR_TIPO)}."
        )
    canal = (data.get("canal") or "email").lower()
    if canal not in CANALES:
        raise ValueError(f"'canal' no válido. Use: {', '.join(CANALES)}.")
    for campo in ("nombre", "asunto", "cuerpo"):
        if not (data.get(campo) or "").strip():
            raise ValueError(f"El campo '{campo}' es obligatorio.")

    plantilla = PlantillaNotificacion(
        codigo=codigo,
        nombre=data["nombre"].strip(),
        tipo_evento=tipo,
        canal=canal,
        asunto=data["asunto"].strip()[:200],
        cuerpo=data["cuerpo"],
        activa=bool(data.get("activa", True)),
        id_administrador=id_administrador,
    )
    db.session.add(plantilla)
    db.session.commit()
    return plantilla


def actualizar_plantilla(id_plantilla, data):
    plantilla = obtener_plantilla(id_plantilla)
    for campo in ("nombre", "asunto", "cuerpo"):
        if campo in data and data[campo]:
            setattr(plantilla, campo, data[campo])
    if "asunto" in data and data["asunto"]:
        plantilla.asunto = data["asunto"][:200]
    if "canal" in data and data["canal"]:
        canal = data["canal"].lower()
        if canal not in CANALES:
            raise ValueError(f"'canal' no válido. Use: {', '.join(CANALES)}.")
        plantilla.canal = canal
    if "activa" in data:
        plantilla.activa = bool(data["activa"])
    db.session.commit()
    return plantilla


def eliminar_plantilla(id_plantilla):
    plantilla = obtener_plantilla(id_plantilla)
    db.session.delete(plantilla)
    db.session.commit()
    return True


# =====================================================================
# RENDER DE PLANTILLAS
# =====================================================================
_MARCADOR = re.compile(r"\{([a-z_]+)\}")


def _contexto_reserva(id_reserva):
    """Arma los valores de los marcadores a partir de la reserva."""
    reserva = db.session.get(Reserva, id_reserva) if id_reserva else None
    if not reserva:
        return {}

    cliente = db.session.get(Cliente, reserva.id_cliente)
    nombre = "Cliente"
    correo = ""
    if cliente:
        usuario = db.session.get(Usuario, cliente.id_usuario)
        if usuario:
            persona = db.session.get(Persona, usuario.id_persona)
            if persona:
                nombre = f"{persona.nombre} {persona.apellido}".strip()
            correo = persona.email if persona else ""
            if not correo:
                correo = usuario.username if "@" in (usuario.username or "") else ""

    cancha = db.session.get(Cancha, reserva.id_cancha)
    return {
        "id_reserva": reserva.id_reserva,
        "codigo_reserva": f"RES-{reserva.id_reserva:05d}",
        "nombre_cliente": nombre,
        "correo_cliente": correo,
        "fecha_reserva": reserva.fecha_reserva.strftime("%d/%m/%Y")
        if reserva.fecha_reserva
        else "",
        "hora_inicio": reserva.hora_inicio.strftime("%H:%M") if reserva.hora_inicio else "",
        "hora_fin": reserva.hora_fin.strftime("%H:%M") if reserva.hora_fin else "",
        "nombre_cancha": cancha.nombre_cancha if cancha else "",
        "monto_total": f"{float(reserva.monto_total):.2f}" if reserva.monto_total else "0.00",
        "estado_reserva": reserva.estado_reserva,
    }


def _renderizar(texto, contexto):
    def reemplazar(m):
        clave = m.group(1)
        if clave in contexto and contexto[clave] not in (None, ""):
            return str(contexto[clave])
        if clave == "nombre_complejo":
            return NOMBRE_COMPLEJO
        # Un marcador sin dato no debe romper el envio.
        return ""

    return _MARCADOR.sub(reemplazar, texto or "")


# =====================================================================
# ENCOLAR (plantilla -> PENDIENTE)
# =====================================================================
def encolar(
    tipo,
    id_reserva=None,
    id_administrador=None,
    canal=None,
    fecha_programada=None,
    clave_idempotencia=None,
    destinatario=None,
    asunto=None,
    cuerpo=None,
    max_intentos=MAX_INTENTOS_POR_DEFECTO,
    id_plantilla=None,
    commit=True,
):
    """Deja la notificacion lista para envio. Nunca manda nada: eso es tarea
    del worker, para no bloquear la reserva."""
    if tipo not in PLANTILLA_POR_TIPO:
        raise ValueError(f"Tipo de notificacion no valido: {tipo}")

    contexto = _contexto_reserva(id_reserva)
    if not destinatario:
        if id_administrador:
            admin = db.session.get(Usuario, id_administrador)
            destinatario = (admin.username if admin else "") or ""
        else:
            destinatario = contexto.get("correo_cliente", "")
    if not destinatario:
        raise ValueError("La notificacion no tiene destinatario.")

    if id_plantilla:
        plantilla = obtener_plantilla(id_plantilla)
    else:
        plantilla = obtener_plantilla_por_codigo(PLANTILLA_POR_TIPO[tipo])

    nueva = Notificacion(
        id_plantilla=plantilla.id_plantilla,
        id_reserva=id_reserva,
        id_administrador=id_administrador,
        tipo=tipo,
        canal=(canal or plantilla.canal or "email"),
        destinatario=destinatario[:150],
        asunto=(asunto or plantilla.asunto)[:200],
        cuerpo=cuerpo or plantilla.cuerpo,
        estado="pendiente",
        intentos=0,
        max_intentos=max(1, int(max_intentos)),
        fecha_programada=fecha_programada or datetime.now(),
        clave_idempotencia=clave_idempotencia,
    )
    # El cuerpo final se renderiza al encolar: el aviso queda con el texto que
    # se mando, aunque despues la reserva cambie.
    nueva.asunto = _renderizar(nueva.asunto, contexto)[:200]
    nueva.cuerpo = _renderizar(nueva.cuerpo, contexto)

    db.session.add(nueva)
    if commit:
        try:
            db.session.commit()
        except IntegrityError:
            # La clave de idempotencia ya existe: este aviso ya estaba encolado.
            db.session.rollback()
            return None
        return nueva

    # Nos llamaron desde un flujo que ya tiene su propia transaccion (por
    # ejemplo el cobro de un pago). Comprobamos la clave con un savepoint y no
    # cerramos nada, para no confirmar a medias el pago.
    try:
        with db.session.begin_nested():
            db.session.flush()
    except IntegrityError:
        return None
    return nueva


def listar_notificaciones(estado=None, tipo=None, id_reserva=None, limite=100):
    consulta = Notificacion.query
    if estado:
        consulta = consulta.filter(Notificacion.estado == estado)
    if tipo:
        consulta = consulta.filter(Notificacion.tipo == tipo)
    if id_reserva:
        consulta = consulta.filter(Notificacion.id_reserva == id_reserva)
    return (
        consulta.order_by(Notificacion.fecha_creacion.desc())
        .limit(min(int(limite), 500))
        .all()
    )


def obtener_notificacion(id_notificacion):
    notificacion = db.session.get(Notificacion, id_notificacion)
    if not notificacion:
        raise ValueError("La notificacion no existe.")
    return notificacion


# =====================================================================
# ENVIO
# =====================================================================
def _enviar_email(destinatario, asunto, cuerpo):
    """SMTP real si hay configuracion; si no, se registra en consola."""
    host = os.getenv("SMTP_HOST")
    if not host:
        print(f"[NOTIFICACION SIMULADA] -> {destinatario} | {asunto}")
        return "simulada: SMTP no configurado"

    puerto = int(os.getenv("SMTP_PORT", "587"))
    usuario = os.getenv("SMTP_USER")
    clave = os.getenv("SMTP_PASSWORD")
    remitente = os.getenv("SMTP_REMITENTE", usuario or "no-reply@localhost")

    mensaje = EmailMessage()
    mensaje["From"] = remitente
    mensaje["To"] = destinatario
    mensaje["Subject"] = asunto
    mensaje.set_content(cuerpo)

    with smtplib.SMTP(host, puerto, timeout=15) as servidor:
        if os.getenv("SMTP_TLS", "1") == "1":
            servidor.starttls()
        if usuario and clave:
            servidor.login(usuario, clave)
        servidor.send_message(mensaje)
    return "enviado por SMTP"


def _enviar_sms(destinatario, cuerpo):
    gateway = os.getenv("SMS_GATEWAY_URL")
    if not gateway:
        print(f"[SMS SIMULADO] -> {destinatario} | {cuerpo[:80]}")
        return "simulada: gateway no configurado"
    raise NotImplementedError("El gateway de SMS no esta implementado.")


def _enviar_push(destinatario, cuerpo):
    print(f"[PUSH SIMULADO] -> {destinatario} | {cuerpo[:80]}")
    return "simulada: push no configurado"


def _enviar(notificacion, simular_fallo=False):
    """Envia por el canal que corresponda. Lanza excepcion si falla, para que
    el llamador la registre y reintente."""
    if simular_fallo:
        raise RuntimeError("Fallo simulado para prueba.")

    if notificacion.canal == "email":
        return _enviar_email(notificacion.destinatario, notificacion.asunto, notificacion.cuerpo)
    if notificacion.canal == "sms":
        return _enviar_sms(notificacion.destinatario, notificacion.cuerpo)
    if notificacion.canal == "push":
        return _enviar_push(notificacion.destinatario, notificacion.cuerpo)
    raise ValueError(f"Canal no soportado: {notificacion.canal}")


def enviar_pendientes(limite=20, simular_fallo=False, solo_id=None):
    """Pase del worker: toma las notificaciones PENDIENTE que ya vencieron y las
    envia. Es la parte asincrona, la reserva no espera por esto.

    Tambien recupera las FALLIDAS que todavia tienen intentos disponibles, para
    que el reintento sea automatico y no dependa de que alguien llame al
    endpoint manual. Las que agotaron sus intentos quedan fuera para siempre.

    solo_id acota el pase a una notificacion concreta; lo usan las pruebas.
    """
    ahora = datetime.now()
    consulta = Notificacion.query.filter(
        Notificacion.estado.in_(("pendiente", "fallido")),
        Notificacion.fecha_programada <= ahora,
        Notificacion.intentos < Notificacion.max_intentos,
    )
    if solo_id is not None:
        consulta = consulta.filter(Notificacion.id_notificacion == solo_id)
    pendientes = (
        consulta.order_by(Notificacion.fecha_programada.asc()).limit(limite).all()
    )

    resultados = {"enviadas": 0, "fallidas": 0, "omitidas": 0}
    for notificacion in pendientes:
        notificacion.intentos += 1
        try:
            detalle = _enviar(notificacion, simular_fallo=simular_fallo)
            notificacion.estado = "enviado"
            notificacion.fecha_envio = datetime.now()
            notificacion.ultimo_error = None
            resultados["enviadas"] += 1
        except Exception as ex:  # noqa: BLE001 - el error se guarda, no se propaga
            notificacion.estado = "fallido"
            notificacion.ultimo_error = str(ex)[:500]
            resultados["fallidas"] += 1
            detalle = str(ex)[:500]

        db.session.add(
            NotificacionIntento(
                id_notificacion=notificacion.id_notificacion,
                numero_intento=notificacion.intentos,
                canal=notificacion.canal,
                estado=notificacion.estado,
                detalle=detalle,
            )
        )
        db.session.commit()

    return resultados


def reintentar(id_notificacion):
    """Devuelve una notificacion fallida a la cola, si le quedan intentos."""
    notificacion = obtener_notificacion(id_notificacion)
    if notificacion.estado == "enviado":
        raise ValueError("La notificacion ya fue enviada.")
    if notificacion.intentos >= notificacion.max_intentos:
        raise ValueError(
            f"La notificacion agoto sus {notificacion.max_intentos} intentos."
        )
    notificacion.estado = "pendiente"
    notificacion.fecha_programada = datetime.now()
    db.session.commit()
    return notificacion


# =====================================================================
# DISPARADORES
# =====================================================================
def _admins_activos():
    return (
        Usuario.query.filter_by(rol="administrador", estado="activo")
        .order_by(Usuario.id_usuario.asc())
        .all()
    )


def _sin_destinatario(funcion):
    """Un aviso sin destinatario no debe tumbar la reserva."""
    try:
        return funcion()
    except ValueError as ex:
        print(f"[NOTIFICACION OMITIDA] {ex}")
        return None


def avisar_confirmacion(reserva, commit=True):
    return _sin_destinatario(
        lambda: encolar(
            "reserva_confirmada", id_reserva=reserva.id_reserva, commit=commit
        )
    )


def avisar_modificacion(reserva, commit=True):
    return _sin_destinatario(
        lambda: encolar(
            "reserva_modificada", id_reserva=reserva.id_reserva, commit=commit
        )
    )


def avisar_cancelacion(reserva, commit=True):
    return _sin_destinatario(
        lambda: encolar(
            "reserva_cancelada", id_reserva=reserva.id_reserva, commit=commit
        )
    )


def avisar_administradores(tipo, reserva, commit=True):
    """Nuevas reservas, cancelaciones y modificaciones al administrador."""
    resultado = []
    for admin in _admins_activos():
        if not admin.username:
            continue
        notificacion = _sin_destinatario(
            lambda a=admin: encolar(
                tipo,
                id_reserva=reserva.id_reserva,
                id_administrador=a.id_usuario,
                destinatario=a.username,
                commit=commit,
            )
        )
        if notificacion:
            resultado.append(notificacion)
    return resultado


def generar_recordatorios(horas_anticipacion=24):
    """Recordatorio antes de la fecha. La clave de idempotencia
    'recordatorio:{id_reserva}' hace que correr el job dos veces el mismo dia
    no genere un segundo aviso."""
    if horas_anticipacion >= 24:
        corte = date.today() + timedelta(days=1)
        reservas = Reserva.query.filter(
            Reserva.estado_reserva.in_(("confirmada", "completada")),
            Reserva.fecha_reserva == corte,
        ).all()
    else:
        ventana = datetime.now() + timedelta(hours=horas_anticipacion)
        reservas = Reserva.query.filter(
            Reserva.estado_reserva == "confirmada",
            Reserva.fecha_reserva == date.today(),
            Reserva.hora_inicio <= ventana.time(),
            Reserva.hora_inicio >= datetime.now().time(),
        ).all()

    creadas = 0
    for reserva in reservas:
        notificacion = _sin_destinatario(
            lambda r=reserva: encolar(
                "recordatorio_reserva",
                id_reserva=r.id_reserva,
                clave_idempotencia=f"recordatorio:{r.id_reserva}:{r.fecha_reserva.isoformat()}",
            )
        )
        if notificacion:
            creadas += 1
    return creadas
