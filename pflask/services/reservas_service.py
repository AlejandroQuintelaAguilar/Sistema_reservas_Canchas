from datetime import datetime, timedelta

from extensions import db
from models.administrador import Administrador
from models.bloqueo import Bloqueo
from models.cancha import Cancha
from models.categoria import Categoria
from models.cliente import Cliente
from models.empleado import Empleado
from models.evento import Evento, evento_cancha
from models.pago import Pago
from models.persona import Persona
from models.reserva import Reserva
from models.usuario import Usuario
from services.auth_service import hash_password

HORA_APERTURA = datetime.strptime("06:00", "%H:%M").time()
HORA_CIERRE = datetime.strptime("23:00", "%H:%M").time()
METODOS_PAGO_VALIDOS = ("efectivo", "tarjeta", "transferencia", "qr")
ESTADOS_VALIDOS_CANCHA = ("disponible", "mantenimiento", "fuera_servicio")
ESTADOS_TERMINALES = ("cancelada", "completada", "expirada")


# ============================================================
# HELPERS
# ============================================================
def _fecha(valor, nombre="fecha"):
    try:
        return datetime.strptime(str(valor).strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise ValueError(f"{nombre} inválida. Use el formato YYYY-MM-DD.")


def _hora(valor, nombre="hora"):
    try:
        return datetime.strptime(str(valor).strip(), "%H:%M").time()
    except (ValueError, TypeError):
        raise ValueError(f"{nombre} inválida. Use el formato HH:MM.")


def _split_nombre(nombre_completo, apellido_explicit=None):
    parts = (nombre_completo or "").strip().split()
    nombre = parts[0] if parts else nombre_completo
    if apellido_explicit and str(apellido_explicit).strip():
        apellido = str(apellido_explicit).strip()
    else:
        apellido = " ".join(parts[1:]) if len(parts) > 1 else (nombre if nombre else "")
    return (nombre or "")[:80], (apellido or "")[:80]


def validar_horario(hora_inicio, hora_fin):
    if hora_inicio < HORA_APERTURA:
        return False, f"La hora de inicio debe ser después de las {HORA_APERTURA.strftime('%H:%M')}."
    if hora_fin > HORA_CIERRE:
        return False, f"La hora de fin debe ser antes de las {HORA_CIERRE.strftime('%H:%M')}."
    return True, None


def expirar_reservas_vencidas():
    limite = datetime.now() - timedelta(minutes=15)
    vencidas = Reserva.query.filter(
        Reserva.estado_reserva == "pendiente",
        Reserva.fecha_creacion < limite,
    ).all()
    for r in vencidas:
        r.estado_reserva = "expirada"
        r.motivo_cancelacion = "Expirada por falta de pago (tiempo límite de 15 min)"
    if vencidas:
        db.session.commit()
    return len(vencidas)


def completar_reservas_pasadas():
    ahora = datetime.now()
    hoy = ahora.date()
    hora_actual = ahora.time()
    completadas = Reserva.query.filter(
        Reserva.estado_reserva == "confirmada"
    ).filter(
        db.or_(
            Reserva.fecha_reserva < hoy,
            db.and_(Reserva.fecha_reserva == hoy, Reserva.hora_fin < hora_actual),
        )
    ).all()
    for r in completadas:
        r.estado_reserva = "completada"
    if completadas:
        db.session.commit()
    return len(completadas)


def _hay_evento(id_cancha, fecha, hora_inicio, hora_fin):
    try:
        with db.session.begin_nested():
            return (
                Evento.query.outerjoin(
                    evento_cancha, Evento.id_evento == evento_cancha.c.id_evento
                )
                .filter(
                    db.or_(
                        Evento.id_cancha == id_cancha,
                        evento_cancha.c.id_cancha == id_cancha,
                    ),
                    Evento.fecha_evento == fecha,
                    Evento.hora_inicio < hora_fin,
                    Evento.hora_fin > hora_inicio,
                )
                .first()
            )
    except Exception:
        return Evento.query.filter(
            Evento.id_cancha == id_cancha,
            Evento.fecha_evento == fecha,
            Evento.hora_inicio < hora_fin,
            Evento.hora_fin > hora_inicio,
        ).first()


def _hay_bloqueo(id_cancha, fecha, hora_inicio, hora_fin):
    return Bloqueo.query.filter(
        Bloqueo.id_cancha == id_cancha,
        Bloqueo.estado == "activo",
        Bloqueo.fecha_inicio <= fecha,
        Bloqueo.fecha_fin >= fecha,
        Bloqueo.hora_inicio < hora_fin,
        Bloqueo.hora_fin > hora_inicio,
    ).first()


def _encontrar_choque(id_cancha, fecha, hora_inicio, hora_fin, excluir_id=None):
    query = Reserva.query.filter(
        Reserva.id_cancha == id_cancha,
        Reserva.fecha_reserva == fecha,
        ~Reserva.estado_reserva.in_(ESTADOS_TERMINALES),
        Reserva.hora_inicio < hora_fin,
        Reserva.hora_fin > hora_inicio,
    )
    if excluir_id:
        query = query.filter(Reserva.id_reserva != excluir_id)
    return query.first()


def _validaciones_reserva(fecha_reserva, hora_inicio, hora_fin, duracion_h=None, id_cancha=None):
    ahora = datetime.now()
    hoy = ahora.date()
    if fecha_reserva < hoy:
        raise ValueError("No se pueden realizar reservas en fechas anteriores a la actual.")
    if fecha_reserva == hoy and hora_inicio <= ahora.time():
        h_actual = ahora.strftime("%H:%M")
        raise ValueError(f"No se pueden realizar reservas en una hora que ya ha transcurrido (hora actual: {h_actual}).")

    dias = (fecha_reserva - hoy).days
    if dias < 0 or dias > 15:
        raise ValueError("La fecha debe estar dentro de los próximos 15 días.")

    if hora_fin <= hora_inicio:
        raise ValueError("La hora fin debe ser mayor que la hora inicio.")

    ok, err = validar_horario(hora_inicio, hora_fin)
    if not ok:
        raise ValueError(err)

    if id_cancha is not None:
        cancha = db.session.get(Cancha, id_cancha)
        if not cancha:
            raise ValueError("Cancha no encontrada.")
        if cancha.estado == "fuera_servicio":
            raise ValueError("La cancha está fuera de servicio.")
        bloqueo = _hay_bloqueo(id_cancha, fecha_reserva, hora_inicio, hora_fin)
        if bloqueo:
            raise ValueError(f"La cancha está bloqueada: {bloqueo.motivo}")
        evento_activo = _hay_evento(id_cancha, fecha_reserva, hora_inicio, hora_fin)
        if evento_activo:
            raise ValueError(
                f"La cancha tiene programado el evento '{evento_activo.nombre_evento}' en ese horario."
            )
        if _encontrar_choque(id_cancha, fecha_reserva, hora_inicio, hora_fin):
            raise ValueError("La cancha no está disponible en ese horario.")
        return cancha
    return None


def _calcular_duracion(fecha_reserva, hora_inicio, datos, duracion_h=None, hora_fin=None):
    if hora_fin is None and datos.get("hora_fin") not in (None, ""):
        hora_fin = _hora(datos["hora_fin"])
    if hora_fin is None and duracion_h is not None:
        hora_fin = (datetime.combine(fecha_reserva, hora_inicio) + timedelta(hours=duracion_h)).time()
    elif hora_fin is not None and duracion_h is None:
        diff = datetime.combine(fecha_reserva, hora_fin) - datetime.combine(fecha_reserva, hora_inicio)
        duracion_h = diff.total_seconds() / 3600
    elif hora_fin is None and duracion_h is None:
        raise ValueError("Indica la duración o la hora fin de la reserva.")
    return hora_fin, duracion_h


# ============================================================
# RESERVAS
# ============================================================
def crear_reserva(datos, current_user=None):
    expirar_reservas_vencidas()
    completar_reservas_pasadas()

    try:
        id_cancha = int(datos["id_cancha"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("id_cancha es obligatorio.")
    if id_cancha <= 0:
        raise ValueError("id_cancha debe ser mayor que 0.")

    fecha_reserva = _fecha(datos.get("fecha_reserva") or datos.get("fecha"))
    hora_inicio = _hora(datos.get("hora_inicio"))

    duracion_h = None
    if datos.get("duracion") not in (None, ""):
        duracion_h = float(datos["duracion"])
        if duracion_h < 1 or duracion_h > 4:
            raise ValueError("La duración debe ser entre 1 y 4 horas.")

    hora_fin, duracion_h = _calcular_duracion(fecha_reserva, hora_inicio, datos, duracion_h)
    if duracion_h <= 0 or duracion_h > 4:
        raise ValueError("La duración debe ser entre 1 y 4 horas.")

    id_cliente = datos.get("id_cliente")
    if id_cliente in (None, ""):
        if current_user is not None:
            cliente = Cliente.query.filter_by(id_usuario=current_user.id_usuario).first()
            if not cliente:
                raise ValueError("El usuario actual no está registrado como cliente.")
            id_cliente = cliente.id_cliente
        else:
            raise ValueError("id_cliente es obligatorio.")
    try:
        id_cliente = int(id_cliente)
    except (TypeError, ValueError):
        raise ValueError("id_cliente inválido.")
    if not db.session.get(Cliente, id_cliente):
        raise ValueError("El cliente indicado no existe.")

    cancha = _validaciones_reserva(fecha_reserva, hora_inicio, hora_fin, duracion_h, id_cancha)

    nueva = Reserva(
        fecha_reserva=fecha_reserva,
        hora_inicio=hora_inicio,
        hora_fin=hora_fin,
        duracion=timedelta(hours=duracion_h),
        estado_reserva="pendiente",
        id_cliente=id_cliente,
        id_cancha=id_cancha,
    )
    db.session.add(nueva)
    db.session.commit()
    db.session.refresh(nueva)

    monto_total = (
        float(nueva.monto_total)
        if nueva.monto_total is not None
        else float(cancha.precio_hora) * duracion_h
    )
    return {
        "mensaje": "Reserva creada. Tienes 15 minutos para pagar antes de que expire.",
        "id_reserva": nueva.id_reserva,
        "monto_total": monto_total,
        "estado": "pendiente",
    }


def crear_reserva_presencial(datos):
    expirar_reservas_vencidas()
    completar_reservas_pasadas()

    try:
        id_cancha = int(datos["id_cancha"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("id_cancha es obligatorio.")
    try:
        id_cliente = int(datos["id_cliente"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("id_cliente es obligatorio.")

    metodo = (datos.get("metodo_pago") or "efectivo").strip().lower()
    if metodo not in METODOS_PAGO_VALIDOS:
        raise ValueError("Método de pago inválido.")

    id_empleado = datos.get("id_empleado")
    if id_empleado not in (None, ""):
        if not db.session.get(Empleado, int(id_empleado)):
            raise ValueError("El empleado indicado no existe.")

    fecha_reserva = _fecha(datos.get("fecha_reserva") or datos.get("fecha"))
    hora_inicio = _hora(datos.get("hora_inicio"))

    duracion_h = None
    if datos.get("duracion") not in (None, ""):
        duracion_h = float(datos["duracion"])
        if duracion_h < 1 or duracion_h > 4:
            raise ValueError("La duración debe ser entre 1 y 4 horas.")

    hora_fin, duracion_h = _calcular_duracion(fecha_reserva, hora_inicio, datos, duracion_h)
    if duracion_h <= 0 or duracion_h > 4:
        raise ValueError("La duración debe ser entre 1 y 4 horas.")

    if not db.session.get(Cliente, id_cliente):
        raise ValueError("El cliente indicado no existe.")

    cancha = _validaciones_reserva(fecha_reserva, hora_inicio, hora_fin, duracion_h, id_cancha)

    nueva = Reserva(
        fecha_reserva=fecha_reserva,
        hora_inicio=hora_inicio,
        hora_fin=hora_fin,
        duracion=timedelta(hours=duracion_h),
        estado_reserva="confirmada",
        id_cliente=id_cliente,
        id_cancha=id_cancha,
    )
    db.session.add(nueva)
    db.session.flush()

    monto_total = (
        float(nueva.monto_total)
        if nueva.monto_total is not None
        else float(cancha.precio_hora) * duracion_h
    )

    pago = Pago(
        metodo_pago=metodo,
        estado_pago="pagado",
        monto=monto_total,
        id_reserva=nueva.id_reserva,
        id_empleado=int(id_empleado) if id_empleado not in (None, "") else None,
    )
    db.session.add(pago)
    db.session.commit()

    return {
        "mensaje": "Reserva presencial creada y confirmada.",
        "id_reserva": nueva.id_reserva,
        "monto_total": monto_total,
        "estado": "confirmada",
        "metodo_pago": metodo,
    }


def _formato_cliente(reserva, cancha):
    return {
        "id_reserva": reserva.id_reserva,
        "cancha": cancha.nombre_cancha,
        "id_cancha": cancha.id_cancha,
        "fecha": str(reserva.fecha_reserva),
        "hora_inicio": str(reserva.hora_inicio)[:5],
        "hora_fin": str(reserva.hora_fin)[:5],
        "duracion": str(reserva.duracion) if reserva.duracion else None,
        "estado": reserva.estado_reserva,
        "precio_hora": float(cancha.precio_hora),
        "motivo_cancelacion": reserva.motivo_cancelacion,
    }


def listar_reservas_cliente(id_cliente, vigentes=False):
    expirar_reservas_vencidas()
    completar_reservas_pasadas()

    query = db.session.query(Reserva, Cancha).join(
        Cancha, Reserva.id_cancha == Cancha.id_cancha
    ).filter(Reserva.id_cliente == id_cliente)

    if vigentes:
        hoy = datetime.now().date()
        query = query.filter(
            Reserva.fecha_reserva >= hoy,
            Reserva.estado_reserva.in_(["pendiente", "confirmada"]),
        ).order_by(Reserva.fecha_reserva.asc(), Reserva.hora_inicio.asc())
    else:
        query = query.order_by(Reserva.fecha_reserva.desc(), Reserva.hora_inicio.desc())

    return [_formato_cliente(r, c) for r, c in query.all()]


def listar_reservas_historial(id_cliente):
    expirar_reservas_vencidas()
    completar_reservas_pasadas()

    rows = db.session.query(Reserva, Cancha).join(
        Cancha, Reserva.id_cancha == Cancha.id_cancha
    ).filter(Reserva.id_cliente == id_cliente).order_by(
        Reserva.fecha_reserva.desc(), Reserva.hora_inicio.desc()
    ).all()

    return [
        {
            "id": r.id_reserva,
            "id_reserva": r.id_reserva,
            "fecha": str(r.fecha_reserva),
            "hora_inicio": str(r.hora_inicio)[:5],
            "hora_fin": str(r.hora_fin)[:5],
            "estado": r.estado_reserva,
            "motivo_cancelacion": r.motivo_cancelacion,
            "cancha": {
                "id": c.id_cancha,
                "id_cancha": c.id_cancha,
                "nombre": c.nombre_cancha,
                "deporte": c.tipo_deporte,
            },
        }
        for r, c in rows
    ]


def cancelar_reserva(id_reserva, motivo=None):
    expirar_reservas_vencidas()
    completar_reservas_pasadas()

    reserva = db.session.get(Reserva, id_reserva)
    if not reserva:
        raise ValueError("Reserva no encontrada.")
    if reserva.estado_reserva in ESTADOS_TERMINALES:
        raise ValueError(f"No se puede cancelar una reserva en estado '{reserva.estado_reserva}'.")

    fecha_hora = datetime.combine(reserva.fecha_reserva, reserva.hora_inicio)
    if datetime.now() > (fecha_hora - timedelta(hours=1)):
        raise ValueError("Solo se puede cancelar hasta 1 hora antes de la reserva.")

    reserva.estado_reserva = "cancelada"
    reserva.motivo_cancelacion = motivo or "Cancelada por el cliente"

    pago = Pago.query.filter_by(id_reserva=id_reserva, estado_pago="pagado").first()
    if pago:
        pago.estado_pago = "reembolsado"

    db.session.commit()
    return {
        "mensaje": "Reserva cancelada exitosamente. Si realizó un pago, el reembolso ha sido procesado.",
        "id_reserva": reserva.id_reserva,
        "estado": "cancelada",
    }


def pagar_reserva(id_reserva, metodo):
    expirar_reservas_vencidas()
    completar_reservas_pasadas()

    reserva = db.session.get(Reserva, id_reserva)
    if not reserva:
        raise ValueError("Reserva no encontrada.")
    if reserva.estado_reserva != "pendiente":
        raise ValueError(
            f"La reserva no está pendiente de pago (estado actual: '{reserva.estado_reserva}')."
        )

    metodo = (metodo or "").strip().lower()
    if metodo not in METODOS_PAGO_VALIDOS:
        raise ValueError("Método de pago inválido.")

    cancha = db.session.get(Cancha, reserva.id_cancha)
    if not cancha:
        raise ValueError("La cancha de la reserva no existe.")

    if reserva.monto_total is not None:
        monto = float(reserva.monto_total)
    else:
        horas = reserva.duracion.total_seconds() / 3600 if reserva.duracion else 1
        monto = float(cancha.precio_hora) * horas

    pago = Pago(
        metodo_pago=metodo,
        estado_pago="pagado",
        monto=monto,
        id_reserva=id_reserva,
    )
    db.session.add(pago)
    reserva.estado_reserva = "confirmada"
    db.session.commit()

    return {
        "mensaje": "Pago registrado. Reserva confirmada.",
        "id_pago": pago.id_pago,
        "id_reserva": reserva.id_reserva,
        "monto_pagado": monto,
        "metodo_pago": metodo,
        "estado_reserva": "confirmada",
    }


# ============================================================
# ADMIN / EMPLEADO
# ============================================================
def listar_reservas_admin(fecha=None, estado=None, id_cancha=None):
    expirar_reservas_vencidas()
    completar_reservas_pasadas()

    query = db.session.query(Reserva, Cancha, Cliente, Persona).join(
        Cancha, Reserva.id_cancha == Cancha.id_cancha
    ).join(
        Cliente, Reserva.id_cliente == Cliente.id_cliente
    ).join(
        Usuario, Cliente.id_usuario == Usuario.id_usuario
    ).join(
        Persona, Usuario.id_persona == Persona.id_persona
    )

    if fecha:
        query = query.filter(Reserva.fecha_reserva == _fecha(fecha, "fecha"))
    if estado:
        estado = str(estado).strip().lower()
        if estado not in ("pendiente", "confirmada", "cancelada", "completada", "expirada"):
            raise ValueError("Estado inválido.")
        query = query.filter(Reserva.estado_reserva == estado)
    if id_cancha:
        query = query.filter(Reserva.id_cancha == int(id_cancha))

    rows = query.order_by(Reserva.fecha_reserva.desc(), Reserva.hora_inicio.desc()).all()

    return [
        {
            "id_reserva": r.id_reserva,
            "cancha": c.nombre_cancha,
            "id_cancha": c.id_cancha,
            "cliente": f"{p.nombre} {p.apellido}",
            "id_cliente": cl.id_cliente,
            "fecha": str(r.fecha_reserva),
            "hora_inicio": str(r.hora_inicio)[:5],
            "hora_fin": str(r.hora_fin)[:5],
            "duracion": str(r.duracion) if r.duracion else None,
            "estado": r.estado_reserva,
            "motivo_cancelacion": r.motivo_cancelacion,
        }
        for r, c, cl, p in rows
    ]


def cancelar_reserva_admin(id_reserva, motivo=None):
    expirar_reservas_vencidas()
    completar_reservas_pasadas()

    reserva = db.session.get(Reserva, id_reserva)
    if not reserva:
        raise ValueError("Reserva no encontrada.")
    if reserva.estado_reserva in ESTADOS_TERMINALES:
        raise ValueError(f"No se puede cancelar una reserva en estado '{reserva.estado_reserva}'.")

    reserva.estado_reserva = "cancelada"
    reserva.motivo_cancelacion = motivo or "Cancelada por administración"

    pago = Pago.query.filter_by(id_reserva=id_reserva, estado_pago="pagado").first()
    if pago:
        pago.estado_pago = "reembolsado"

    db.session.commit()
    return {
        "mensaje": "Reserva cancelada por administración.",
        "id_reserva": reserva.id_reserva,
        "motivo": reserva.motivo_cancelacion,
    }


def modificar_reserva_admin(id_reserva, datos):
    expirar_reservas_vencidas()
    completar_reservas_pasadas()

    reserva = db.session.get(Reserva, id_reserva)
    if not reserva:
        raise ValueError("Reserva no encontrada.")
    if reserva.estado_reserva in ESTADOS_TERMINALES:
        raise ValueError(f"No se puede modificar una reserva en estado '{reserva.estado_reserva}'.")

    try:
        id_cancha = int(datos.get("id_cancha", reserva.id_cancha))
    except (TypeError, ValueError):
        raise ValueError("id_cancha inválido.")

    nueva_fecha = _fecha(datos.get("fecha_reserva"))
    nueva_hora = _hora(datos.get("hora_inicio"))
    nueva_duracion = float(datos.get("duracion", 1))
    if nueva_duracion < 1 or nueva_duracion > 4:
        raise ValueError("La duración debe ser entre 1 y 4 horas.")
    nueva_hora_fin = (
        datetime.combine(nueva_fecha, nueva_hora) + timedelta(hours=nueva_duracion)
    ).time()

    hoy = datetime.now().date()
    dias = (nueva_fecha - hoy).days
    if dias < 1 or dias > 15:
        raise ValueError("La nueva fecha debe estar entre 1 y 15 días de anticipación.")
    if nueva_hora_fin <= nueva_hora:
        raise ValueError("La hora fin debe ser mayor que la hora inicio.")

    ok, err = validar_horario(nueva_hora, nueva_hora_fin)
    if not ok:
        raise ValueError(err)

    cancha_nueva = db.session.get(Cancha, id_cancha)
    if not cancha_nueva:
        raise ValueError("Cancha no encontrada.")

    bloqueo = _hay_bloqueo(id_cancha, nueva_fecha, nueva_hora, nueva_hora_fin)
    if bloqueo:
        raise ValueError(f"La cancha está bloqueada: {bloqueo.motivo}")

    evento_activo = _hay_evento(id_cancha, nueva_fecha, nueva_hora, nueva_hora_fin)
    if evento_activo:
        raise ValueError(
            f"La cancha tiene programado el evento '{evento_activo.nombre_evento}' en el nuevo horario."
        )

    choque = _encontrar_choque(id_cancha, nueva_fecha, nueva_hora, nueva_hora_fin, excluir_id=id_reserva)
    if choque:
        raise ValueError("La cancha no está disponible en el nuevo horario.")

    reserva.id_cancha = id_cancha
    reserva.fecha_reserva = nueva_fecha
    reserva.hora_inicio = nueva_hora
    reserva.hora_fin = nueva_hora_fin
    reserva.duracion = timedelta(hours=nueva_duracion)

    nuevo_monto = float(cancha_nueva.precio_hora) * nueva_duracion
    reserva.monto_total = nuevo_monto

    db.session.commit()

    return {
        "mensaje": "Reserva modificada exitosamente",
        "id_reserva": reserva.id_reserva,
        "nuevo_monto": nuevo_monto,
        "nueva_fecha": str(reserva.fecha_reserva),
        "nueva_hora_inicio": str(reserva.hora_inicio)[:5],
        "nueva_hora_fin": str(reserva.hora_fin)[:5],
        "nueva_cancha": cancha_nueva.nombre_cancha,
        "id_cancha": cancha_nueva.id_cancha,
    }


# ============================================================
# CLIENTES
# ============================================================
def listar_clientes():
    filas = db.session.query(Cliente, Persona).join(
        Usuario, Cliente.id_usuario == Usuario.id_usuario
    ).join(Persona, Usuario.id_persona == Persona.id_persona).all()

    return [
        {
            "id_cliente": c.id_cliente,
            "nombre_completo": f"{p.nombre} {p.apellido}".strip(),
            "ci": p.ci,
            "email": p.email,
        }
        for c, p in filas
    ]


def obtener_id_cliente_actual(usuario):
    if usuario is None:
        raise ValueError("No autenticado.")
    cliente = Cliente.query.filter_by(id_usuario=usuario.id_usuario).first()
    if not cliente:
        raise ValueError("El usuario actual no está registrado como cliente.")
    return cliente.id_cliente


def crear_cliente(datos):
    nombre_in = (datos.get("nombre") or "").strip()
    apellido_in = datos.get("apellido")
    ci = (datos.get("ci") or "").strip()
    celular = (datos.get("celular") or "").strip() or None
    email = (datos.get("email") or "").strip().lower() or None
    username = (datos.get("username") or "").strip()
    contrasena = datos.get("contrasena") or datos.get("password") or ""

    if not nombre_in or not ci or not username or not contrasena:
        raise ValueError("Nombre, CI, username y contraseña son obligatorios.")
    if len(contrasena) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres.")
    if email and "@" not in email:
        raise ValueError("email inválido.")

    nombre, apellido = _split_nombre(nombre_in, apellido_in)

    if Persona.query.filter(Persona.ci == ci).first():
        raise ValueError(f"Ya existe una persona con CI '{ci}'.")
    if email and Persona.query.filter(Persona.email.ilike(email)).first():
        raise ValueError("Ese email ya está registrado.")
    if Usuario.query.filter(Usuario.username.ilike(username)).first():
        raise ValueError(f"Ya existe un usuario con username '{username}'.")

    persona = Persona(
        nombre=nombre,
        apellido=apellido,
        ci=ci,
        celular=celular,
        email=email,
    )
    db.session.add(persona)
    db.session.flush()

    usuario = Usuario(
        username=username,
        contrasena=hash_password(contrasena),
        rol="cliente",
        id_persona=persona.id_persona,
    )
    db.session.add(usuario)
    db.session.flush()

    cliente = Cliente(
        id_usuario=usuario.id_usuario,
        fecha_afiliacion=datetime.now().date(),
    )
    db.session.add(cliente)
    db.session.commit()

    return {
        "mensaje": "Cliente registrado exitosamente.",
        "id_cliente": cliente.id_cliente,
        "nombre_completo": f"{persona.nombre} {persona.apellido}".strip(),
        "ci": persona.ci,
        "email": persona.email,
        "username": usuario.username,
    }


# ============================================================
# BLOQUEOS
# ============================================================
def listar_bloqueos(activos_only=True):
    query = db.session.query(Bloqueo, Cancha).join(
        Cancha, Bloqueo.id_cancha == Cancha.id_cancha
    )
    if activos_only:
        query = query.filter(Bloqueo.estado == "activo")
    filas = query.order_by(Bloqueo.fecha_inicio.desc()).all()

    return [
        {
            "id_bloqueo": b.id_bloqueo,
            "cancha": c.nombre_cancha,
            "id_cancha": c.id_cancha,
            "fecha_inicio": str(b.fecha_inicio),
            "fecha_fin": str(b.fecha_fin),
            "hora_inicio": str(b.hora_inicio)[:5],
            "hora_fin": str(b.hora_fin)[:5],
            "motivo": b.motivo,
            "estado": b.estado,
        }
        for b, c in filas
    ]


def crear_bloqueo(datos):
    try:
        id_cancha = int(datos["id_cancha"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("id_cancha es obligatorio.")
    try:
        id_administrador = int(datos["id_administrador"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("id_administrador es obligatorio.")

    fecha_inicio = _fecha(datos.get("fecha_inicio"), "fecha_inicio")
    fecha_fin = _fecha(datos.get("fecha_fin"), "fecha_fin")
    hora_inicio = _hora(datos.get("hora_inicio"), "hora_inicio")
    hora_fin = _hora(datos.get("hora_fin"), "hora_fin")
    motivo = str(datos.get("motivo") or "").strip()

    if fecha_fin < fecha_inicio:
        raise ValueError("La fecha fin no puede ser antes que la fecha inicio.")
    if hora_fin <= hora_inicio:
        raise ValueError("La hora fin debe ser mayor que la hora inicio.")
    if not motivo:
        raise ValueError("El motivo del bloqueo es obligatorio.")

    ok, err = validar_horario(hora_inicio, hora_fin)
    if not ok:
        raise ValueError(err)

    if not db.session.get(Cancha, id_cancha):
        raise ValueError("Cancha no encontrada.")
    if not db.session.get(Administrador, id_administrador):
        raise ValueError("El administrador indicado no existe.")

    nuevo = Bloqueo(
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        hora_inicio=hora_inicio,
        hora_fin=hora_fin,
        motivo=motivo,
        estado="activo",
        id_cancha=id_cancha,
        id_administrador=id_administrador,
    )
    db.session.add(nuevo)
    db.session.commit()

    return {"mensaje": "Bloqueo registrado exitosamente", "id_bloqueo": nuevo.id_bloqueo}


def eliminar_bloqueo(id_bloqueo):
    bloqueo = db.session.get(Bloqueo, id_bloqueo)
    if not bloqueo:
        raise ValueError("Bloqueo no encontrado.")
    bloqueo.estado = "inactivo"
    db.session.commit()
    return {"mensaje": "Bloqueo desactivado exitosamente", "id_bloqueo": bloqueo.id_bloqueo}


# ============================================================
# CRUD CANCHAS (ADMIN)
# ============================================================
def admin_crear_cancha(datos):
    nombre = (datos.get("nombre_cancha") or "").strip()
    tipo_deporte = (datos.get("tipo_deporte") or "").strip()
    precio = datos.get("precio_hora")
    try:
        precio = float(precio)
    except (TypeError, ValueError):
        raise ValueError("precio_hora debe ser un número válido.")
    if precio <= 0:
        raise ValueError("El precio por hora debe ser mayor a 0.")

    if not nombre or not tipo_deporte:
        raise ValueError("Nombre y tipo de deporte son obligatorios.")

    try:
        id_categoria = int(datos["id_categoria"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("id_categoria es obligatorio.")
    try:
        id_administrador = int(datos["id_administrador"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("id_administrador es obligatorio.")

    if not db.session.get(Categoria, id_categoria):
        raise ValueError("Categoría no encontrada.")
    if not db.session.get(Administrador, id_administrador):
        raise ValueError("El administrador indicado no existe.")

    estado = str(datos.get("estado") or "disponible").strip().lower()
    if estado not in ESTADOS_VALIDOS_CANCHA:
        raise ValueError("Estado inválido. Use: disponible, mantenimiento o fuera_servicio.")

    nueva = Cancha(
        nombre_cancha=nombre,
        tipo_deporte=tipo_deporte,
        precio_hora=precio,
        techada=bool(datos.get("techada", False)),
        ubicacion=(datos.get("ubicacion") or "").strip() or None,
        superficie=(datos.get("superficie") or "").strip() or None,
        estado=estado,
        id_categoria=id_categoria,
        id_administrador=id_administrador,
    )
    db.session.add(nueva)
    db.session.commit()

    return {"mensaje": "Cancha creada exitosamente", "id_cancha": nueva.id_cancha}


def admin_editar_cancha(id_cancha, datos):
    cancha = db.session.get(Cancha, id_cancha)
    if not cancha:
        raise ValueError("Cancha no encontrada.")

    if datos.get("nombre_cancha") is not None:
        nombre = str(datos["nombre_cancha"]).strip()
        if not nombre:
            raise ValueError("El nombre no puede estar vacío.")
        cancha.nombre_cancha = nombre

    if datos.get("tipo_deporte") is not None:
        tipo_deporte = str(datos["tipo_deporte"]).strip()
        if not tipo_deporte:
            raise ValueError("El tipo de deporte no puede estar vacío.")
        cancha.tipo_deporte = tipo_deporte

    if "precio_hora" in datos:
        precio = float(datos["precio_hora"])
        if precio <= 0:
            raise ValueError("El precio por hora debe ser mayor a 0.")
        cancha.precio_hora = precio

    if "techada" in datos:
        cancha.techada = bool(datos["techada"])

    if "ubicacion" in datos:
        cancha.ubicacion = str(datos["ubicacion"]).strip() or None

    if "superficie" in datos:
        cancha.superficie = str(datos["superficie"]).strip() or None

    if "estado" in datos:
        estado = str(datos["estado"]).strip().lower()
        if estado not in ESTADOS_VALIDOS_CANCHA:
            raise ValueError("Estado inválido. Use: disponible, mantenimiento o fuera_servicio.")
        cancha.estado = estado

    if "id_categoria" in datos:
        id_categoria = int(datos["id_categoria"])
        if not db.session.get(Categoria, id_categoria):
            raise ValueError("Categoría no encontrada.")
        cancha.id_categoria = id_categoria

    if "id_administrador" in datos:
        id_administrador = int(datos["id_administrador"])
        if not db.session.get(Administrador, id_administrador):
            raise ValueError("El administrador indicado no existe.")
        cancha.id_administrador = id_administrador

    db.session.commit()
    return {"mensaje": "Cancha actualizada", "id_cancha": cancha.id_cancha}


def admin_eliminar_cancha(id_cancha):
    cancha = db.session.get(Cancha, id_cancha)
    if not cancha:
        raise ValueError("Cancha no encontrada.")

    hoy = datetime.now().date()
    reservas_activas = Reserva.query.filter(
        Reserva.id_cancha == id_cancha,
        Reserva.fecha_reserva >= hoy,
        Reserva.estado_reserva.in_(["pendiente", "confirmada"]),
    ).count()
    if reservas_activas > 0:
        raise ValueError(f"No se puede eliminar: hay {reservas_activas} reserva(s) activas.")

    cancha.estado = "fuera_servicio"
    db.session.commit()
    return {"mensaje": "Cancha desactivada (fuera de servicio)"}


# ============================================================
# CRUD CATEGORÍAS (ADMIN)
# ============================================================
def admin_crear_categoria(datos):
    nombre = (datos.get("nombre") or "").strip()
    descripcion = (datos.get("descripcion") or "").strip() or None
    if not nombre:
        raise ValueError("El nombre es obligatorio.")
    if Categoria.query.filter(Categoria.nombre.ilike(nombre)).first():
        raise ValueError(f"Ya existe una categoría '{nombre}'.")

    nueva = Categoria(nombre=nombre, descripcion=descripcion)
    db.session.add(nueva)
    db.session.commit()
    return {"mensaje": "Categoría creada exitosamente", "id_categoria": nueva.id_categoria}


def admin_editar_categoria(id_categoria, datos):
    cat = db.session.get(Categoria, id_categoria)
    if not cat:
        raise ValueError("Categoría no encontrada.")

    nombre = (datos.get("nombre") or "").strip()
    descripcion = (datos.get("descripcion") or "").strip() or None
    if not nombre:
        raise ValueError("El nombre es obligatorio.")

    existente = Categoria.query.filter(Categoria.nombre.ilike(nombre)).first()
    if existente and existente.id_categoria != id_categoria:
        raise ValueError("Ya existe otra categoría con ese nombre.")

    cat.nombre = nombre
    cat.descripcion = descripcion
    db.session.commit()
    return {"mensaje": "Categoría actualizada", "id_categoria": cat.id_categoria}


def admin_eliminar_categoria(id_categoria):
    cat = db.session.get(Categoria, id_categoria)
    if not cat:
        raise ValueError("Categoría no encontrada.")
    if Cancha.query.filter_by(id_categoria=id_categoria).count() > 0:
        raise ValueError("No se puede eliminar: hay canchas con esta categoría.")

    db.session.delete(cat)
    db.session.commit()
    return {"mensaje": "Categoría eliminada"}