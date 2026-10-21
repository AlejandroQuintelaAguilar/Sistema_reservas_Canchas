"""Reportes del administrador.

Reglas del documento de requisitos:
- Tipos: reservas, ocupacion e ingresos.
- Filtros: rango de fechas (fin >= inicio), cancha, cliente y estado.
- INGRESOS = pagos aprobados - devoluciones (no es la suma de reservas).
- OCUPACION = horas reservadas confirmadas / horas disponibles.
- Sin datos -> mensaje "sin datos".
"""
from datetime import date

from sqlalchemy import text

from extensions import db
from models.reporte import Reporte
from models.administrador import Administrador
from models.cancha import Cancha

TIPOS_REPORTE = ("reservas", "ocupacion", "ingresos")

# Estados reales de la base. El documento los llama reservada, confirmada,
# cancelada y finalizada; "expirada" es el quinto estado que agregamos para
# que las reservas no cobradas no queden invisibles.
ESTADOS_REPORTE = ("pendiente", "confirmada", "completada", "cancelada", "expirada")
ETIQUETA_ESTADO = {
    "pendiente": "reservada",
    "confirmada": "confirmada",
    "completada": "finalizada",
    "cancelada": "cancelada",
    "expirada": "expirada",
}

# Solo estas reservas cuentan como ocupacion: una reserva pendiente o expirada
# no ocupa la cancha porque nunca se cobro.
ESTADOS_OCUPAN = ("confirmada", "completada")

DIAS_SEMANA = {
    0: "lunes", 1: "martes", 2: "miercoles", 3: "jueves",
    4: "viernes", 5: "sabado", 6: "domingo",
}

HORARIO_APERTURA_POR_DEFECTO = 6
HORARIO_CIERRE_POR_DEFECTO = 23


def _validar_rango(fecha_inicio, fecha_fin):
    if not fecha_inicio or not fecha_fin:
        raise ValueError("Debe indicar fecha_inicio y fecha_fin (AAAA-MM-DD).")
    if fecha_inicio > fecha_fin:
        raise ValueError("La fecha de inicio no puede ser mayor que la fecha fin.")


def _validar_filtros(tipo, estado, id_cancha, id_cliente):
    if tipo and tipo not in TIPOS_REPORTE:
        raise ValueError(f"Tipo no válido. Use: {', '.join(TIPOS_REPORTE)}.")
    if estado and estado not in ESTADOS_REPORTE:
        raise ValueError(
            f"Estado no válido. Use: {', '.join(ESTADOS_REPORTE)}."
        )
    if id_cancha is not None and int(id_cancha) <= 0:
        raise ValueError("id_cancha debe ser un entero mayor que 0.")
    if id_cliente is not None and int(id_cliente) <= 0:
        raise ValueError("id_cliente debe ser un entero mayor que 0.")


def _normalizar_filtros(filtros):
    """Lee los filtros opcionales y los deja listos para el WHERE."""
    f = filtros or {}
    id_cancha = f.get("id_cancha")
    id_cliente = f.get("id_cliente")
    return {
        "id_cancha": int(id_cancha) if id_cancha not in (None, "") else None,
        "id_cliente": int(id_cliente) if id_cliente not in (None, "") else None,
        "estado": f.get("estado") or None,
    }


def _dia_atendido(cancha, dia):
    """El texto de dias_atencion es libre: null o 'todos' significa todos."""
    if not cancha.dias_atencion:
        return True
    declarados = {
        d.strip().lower() for d in cancha.dias_atencion.split(",") if d.strip()
    }
    if not declarados or declarados & {"todos", "todos los dias", "diario"}:
        return True
    nombre = DIAS_SEMANA[dia.weekday()]
    return nombre in declarados or nombre.rstrip("s") in declarados


def _horas_dia(cancha):
    apertura = (
        cancha.horario_apertura.hour
        if cancha.horario_apertura
        else HORARIO_APERTURA_POR_DEFECTO
    )
    cierre = (
        cancha.horario_cierre.hour + (1 if cancha.horario_cierre.minute else 0)
        if cancha.horario_cierre
        else HORARIO_CIERRE_POR_DEFECTO
    )
    return max(cierre - apertura, 0)


def _horas_disponibles(cancha_id, fecha_inicio, fecha_fin):
    """Horas reales de esa cancha en el rango, segun su horario y dias."""
    cancha = db.session.get(Cancha, cancha_id)
    if not cancha:
        return 0
    por_dia = _horas_dia(cancha)
    if por_dia == 0:
        return 0
    dias = 0
    cursor = fecha_inicio
    while cursor <= fecha_fin:
        if _dia_atendido(cancha, cursor):
            dias += 1
        cursor = date.fromordinal(cursor.toordinal() + 1)
    return dias * por_dia


# =====================================================================
# CRUD de la tabla reporte (metadatos)
# =====================================================================
def listar_reportes():
    return Reporte.query.order_by(Reporte.fecha_generado.desc()).all()


def obtener_reporte_por_id(id_reporte):
    reporte = db.session.get(Reporte, id_reporte)
    if not reporte:
        raise ValueError("El reporte no existe.")
    return reporte


def generar_reporte(datos):
    if datos.get("id_administrador"):
        administrador = db.session.get(Administrador, datos["id_administrador"])
        if not administrador:
            raise ValueError("El administrador indicado no existe.")

    nuevo = Reporte(
        tipo=datos["tipo"],
        fecha_generado=datos.get("fecha_generado") or date.today(),
        descripcion=datos.get("descripcion"),
        id_administrador=datos.get("id_administrador") or None,
    )
    db.session.add(nuevo)
    db.session.commit()
    return nuevo


def registrar_generacion(tipo, id_administrador, descripcion=None):
    """Rastro automatico: deja constancia cada vez que se genera un reporte."""
    if not id_administrador:
        return None
    if not db.session.get(Administrador, id_administrador):
        return None
    nuevo = Reporte(
        tipo=tipo,
        fecha_generado=date.today(),
        descripcion=descripcion,
        id_administrador=id_administrador,
    )
    db.session.add(nuevo)
    db.session.commit()
    return nuevo


def eliminar_reporte(id_reporte):
    reporte = obtener_reporte_por_id(id_reporte)
    db.session.delete(reporte)
    db.session.commit()
    return True


# =====================================================================
# REPORTES
# =====================================================================
def reporte_reservas(fecha_inicio, fecha_fin, filtros=None):
    _validar_rango(fecha_inicio, fecha_fin)
    f = _normalizar_filtros(filtros)
    _validar_filtros("reservas", f["estado"], f["id_cancha"], f["id_cliente"])

    condiciones = ["r.id_reserva IS NOT NULL"]
    params = {"fi": fecha_inicio, "ff": fecha_fin}
    if f["id_cancha"]:
        condiciones.append("r.id_cancha = :cancha")
        params["cancha"] = f["id_cancha"]
    if f["id_cliente"]:
        condiciones.append("r.id_cliente = :cliente")
        params["cliente"] = f["id_cliente"]
    if f["estado"]:
        condiciones.append("r.estado_reserva = :estado")
        params["estado"] = f["estado"]

    sql = text(f"""
        SELECT
            c.id_cancha,
            c.nombre_cancha,
            c.tipo_deporte,
            COUNT(r.id_reserva) AS total,
            COUNT(r.id_reserva) FILTER (WHERE r.estado_reserva = 'pendiente')  AS reservadas,
            COUNT(r.id_reserva) FILTER (WHERE r.estado_reserva = 'confirmada') AS confirmadas,
            COUNT(r.id_reserva) FILTER (WHERE r.estado_reserva = 'completada') AS finalizadas,
            COUNT(r.id_reserva) FILTER (WHERE r.estado_reserva = 'cancelada')  AS canceladas,
            COUNT(r.id_reserva) FILTER (WHERE r.estado_reserva = 'expirada')   AS expiradas
        FROM cancha c
        JOIN reserva r
               ON r.id_cancha = c.id_cancha
              AND r.fecha_reserva BETWEEN :fi AND :ff
        WHERE {' AND '.join(condiciones)}
        GROUP BY c.id_cancha, c.nombre_cancha, c.tipo_deporte
        ORDER BY total DESC, c.nombre_cancha ASC
    """)
    filas = db.session.execute(sql, params).mappings().all()
    return [dict(f) for f in filas]


def reporte_ocupacion(fecha_inicio, fecha_fin, filtros=None):
    _validar_rango(fecha_inicio, fecha_fin)
    f = _normalizar_filtros(filtros)
    _validar_filtros("ocupacion", f["estado"], f["id_cancha"], f["id_cliente"])

    condiciones = ["r.id_reserva IS NOT NULL"]
    params = {"fi": fecha_inicio, "ff": fecha_fin}
    estados_ocupan = ", ".join(f"'{e}'" for e in ESTADOS_OCUPAN)
    condiciones.append(f"r.estado_reserva IN ({estados_ocupan})")
    if f["id_cancha"]:
        condiciones.append("r.id_cancha = :cancha")
        params["cancha"] = f["id_cancha"]
    if f["id_cliente"]:
        condiciones.append("r.id_cliente = :cliente")
        params["cliente"] = f["id_cliente"]
    if f["estado"]:
        condiciones.append("r.estado_reserva = :estado")
        params["estado"] = f["estado"]

    sql = text(f"""
        SELECT
            c.id_cancha,
            c.nombre_cancha,
            c.tipo_deporte,
            COUNT(r.id_reserva) AS reservas_confirmadas,
            COALESCE(SUM(EXTRACT(EPOCH FROM (r.hora_fin - r.hora_inicio)) / 3600.0), 0)
                AS horas_reservadas
        FROM cancha c
        JOIN reserva r
               ON r.id_cancha = c.id_cancha
              AND r.fecha_reserva BETWEEN :fi AND :ff
        WHERE {' AND '.join(condiciones)}
        GROUP BY c.id_cancha, c.nombre_cancha, c.tipo_deporte
        ORDER BY horas_reservadas DESC, c.nombre_cancha ASC
    """)
    filas = db.session.execute(sql, params).mappings().all()

    resultado = []
    for fila in filas:
        horas = round(float(fila["horas_reservadas"] or 0), 2)
        disponibles = _horas_disponibles(fila["id_cancha"], fecha_inicio, fecha_fin)
        resultado.append({
            "id_cancha": fila["id_cancha"],
            "nombre_cancha": fila["nombre_cancha"],
            "tipo_deporte": fila["tipo_deporte"],
            "reservas_confirmadas": fila["reservas_confirmadas"],
            "horas_reservadas": horas,
            "horas_disponibles": disponibles,
            "porcentaje_ocupacion": (
                round((horas / disponibles) * 100, 2) if disponibles else 0
            ),
        })
    return resultado


def reporte_ingresos(fecha_inicio, fecha_fin, filtros=None):
    _validar_rango(fecha_inicio, fecha_fin)
    f = _normalizar_filtros(filtros)
    _validar_filtros("ingresos", f["estado"], f["id_cancha"], f["id_cliente"])

    # Ingresos = pagos aprobados - devoluciones. Se fecha por la reserva, que es
    # lo que el administrador compara al cobrar el mismo rango en los 3 reportes.
    condiciones = ["p.id_pago IS NOT NULL"]
    params = {"fi": fecha_inicio, "ff": fecha_fin}
    if f["id_cancha"]:
        condiciones.append("r.id_cancha = :cancha")
        params["cancha"] = f["id_cancha"]
    if f["id_cliente"]:
        condiciones.append("r.id_cliente = :cliente")
        params["cliente"] = f["id_cliente"]
    if f["estado"]:
        # El estado del filtro es el de la reserva, no el del pago.
        condiciones.append("r.estado_reserva = :estado")
        params["estado"] = f["estado"]

    sql = text(f"""
        SELECT
            c.id_cancha,
            c.nombre_cancha,
            c.tipo_deporte,
            COUNT(p.id_pago) AS cantidad_pagos,
            COALESCE(SUM(p.monto) FILTER (WHERE p.estado_pago = 'aprobado'), 0)
                - COALESCE(SUM(p.monto_devuelto) FILTER (
                        WHERE p.estado_pago IN ('aprobado', 'devuelto')), 0) AS total_ingresos,
            COALESCE(SUM(p.monto) FILTER (
                WHERE p.estado_pago IN ('pendiente', 'pendiente_validacion')), 0) AS total_pendiente,
            COALESCE(SUM(p.monto_devuelto) FILTER (
                WHERE p.estado_pago IN ('aprobado', 'devuelto')), 0) AS total_reembolsado
        FROM cancha c
        JOIN reserva r
               ON r.id_cancha = c.id_cancha
              AND r.fecha_reserva BETWEEN :fi AND :ff
        JOIN pago p ON p.id_reserva = r.id_reserva
        WHERE {' AND '.join(condiciones)}
        GROUP BY c.id_cancha, c.nombre_cancha, c.tipo_deporte
        ORDER BY total_ingresos DESC, c.nombre_cancha ASC
    """)
    filas = db.session.execute(sql, params).mappings().all()
    return [
        {
            "id_cancha": f["id_cancha"],
            "nombre_cancha": f["nombre_cancha"],
            "tipo_deporte": f["tipo_deporte"],
            "cantidad_pagos": f["cantidad_pagos"],
            "total_ingresos": round(float(f["total_ingresos"] or 0), 2),
            "total_pendiente": round(float(f["total_pendiente"] or 0), 2),
            "total_reembolsado": round(float(f["total_reembolsado"] or 0), 2),
        }
        for f in filas
    ]


REPORTES = {
    "reservas": reporte_reservas,
    "ocupacion": reporte_ocupacion,
    "ingresos": reporte_ingresos,
}
