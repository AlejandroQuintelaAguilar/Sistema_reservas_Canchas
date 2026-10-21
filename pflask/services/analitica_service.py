"""Motor de la Analítica de Datos (sección 7 del documento de negocio).

La diferencia con Reportes es el ciclo de vida:

    Reporte  -> se calcula al vuelo, no se guarda el resultado.
    Análisis -> se calcula, se PERSISTE con sus parámetros y sus métricas, y
                después se consulta, se filtra y se exporta.

Por eso aquí lo importante no es solo la consulta: es que el resultado quede
guardado en `analisis_generado` y que se pueda volver a leer aunque los datos
originales cambien.
"""

from datetime import date, datetime

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models.analisis_generado import AnalisisGenerado

# ---------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------
TIPOS_ANALISIS = ("reservas", "pagos", "canchas", "clientes")

ETIQUETA_TIPO = {
    "reservas": "Reservas",
    "pagos": "Pagos",
    "canchas": "Canchas",
    "clientes": "Clientes",
}

# Estados de reserva tal como están en la base. La etiqueta de negocio los
# renombra (pendiente -> reservada, completada -> finalizada).
RESERVAS_QUE_OCUPAN = ("confirmada", "completada")
RESERVAS_COBRADAS = ("confirmada", "completada")

# Ingresos = pagos aprobados - devoluciones (regla del documento, sección 6).
# 'devuelto' entra en el filtro porque guarda lo devuelto en monto_devuelto.
PAGOS_QUE_CUENTAN = ("aprobado", "devuelto")


# ---------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------
def _filas(query, params=None):
    """Ejecuta SQL crudo y devuelve filas como diccionarios con tipos simples."""
    resultado = db.session.execute(text(query), params or {})
    columnas = list(resultado.keys())
    filas = []
    for fila in resultado.fetchall():
        item = {}
        for i, columna in enumerate(columnas):
            valor = fila[i]
            if isinstance(valor, datetime):
                item[columna] = valor.isoformat()
            elif isinstance(valor, date):
                item[columna] = valor.isoformat()
            elif isinstance(valor, (int, float, str, bool)) or valor is None:
                item[columna] = valor
            else:
                item[columna] = str(valor)
        filas.append(item)
    return filas


def _uno(query, params=None, por_defecto=0):
    filas = _filas(query, params)
    if not filas:
        return por_defecto
    valor = next(iter(filas[0].values()))
    return valor if valor is not None else por_defecto


def _redondear(valor, decimales=2):
    try:
        return round(float(valor), decimales)
    except (TypeError, ValueError):
        return 0.0


def _tasa(parte, total):
    """Porcentaje seguro: si no hay denominador, la tasa es 0 y no revienta."""
    try:
        parte = float(parte or 0)
        total = float(total or 0)
    except (TypeError, ValueError):
        return 0.0
    if total <= 0:
        return 0.0
    return round(parte * 100.0 / total, 2)


def _lista_ids(valores):
    """Normaliza un filtro de ids a enteros, descartando lo que no sea número."""
    if valores in (None, "", []):
        return []
    if not isinstance(valores, (list, tuple)):
        valores = [valores]
    salida = []
    for v in valores:
        try:
            salida.append(int(v))
        except (TypeError, ValueError):
            continue
    return salida


# ---------------------------------------------------------------------
# Métricas por tipo de análisis
# ---------------------------------------------------------------------
def _analisis_reservas(fi, ff, params):
    """Demanda por horario, tasas de cancelación/expiración y por cancha."""
    filtros = {
        "id_cancha": _lista_ids(params.get("id_cancha")),
        "id_cliente": _lista_ids(params.get("id_cliente")),
        "estado": [str(e).strip() for e in (params.get("estado") or []) if str(e).strip()],
    }

    cond = ["r.fecha_reserva BETWEEN :fi AND :ff"]
    if filtros["id_cancha"]:
        cond.append("r.id_cancha = ANY(:id_cancha)")
    if filtros["id_cliente"]:
        cond.append("r.id_cliente = ANY(:id_cliente)")
    if filtros["estado"]:
        cond.append("r.estado_reserva = ANY(:estado)")
    where = " AND ".join(cond)

    # Serie por día: cuántas reservas y cuántas horas se pidieron.
    por_dia = _filas(
        f"""
        SELECT r.fecha_reserva::date            AS fecha,
               COUNT(*)                          AS reservas,
               COUNT(*) FILTER (WHERE r.estado_reserva = ANY(:ocupan)) AS reservas_cobradas,
               COALESCE(SUM(EXTRACT(EPOCH FROM (r.hora_fin - r.hora_inicio)) / 3600.0), 0)
                                                 AS horas_solicitadas
          FROM reserva r
         WHERE {where}
         GROUP BY r.fecha_reserva::date
         ORDER BY 1
        """,
        {
            "fi": fi, "ff": ff, "ocupan": list(RESERVAS_QUE_OCUPAN),
            "id_cancha": filtros["id_cancha"], "id_cliente": filtros["id_cliente"],
            "estado": filtros["estado"],
        },
    )
    for f in por_dia:
        f["horas_solicitadas"] = _redondear(f["horas_solicitadas"])

    # HORARIOS DE MAYOR DEMANDA: la hora de arranque, no el día.
    por_hora = _filas(
        f"""
        SELECT r.hora_inicio::time                          AS hora,
               COUNT(*)                                    AS reservas,
               COALESCE(SUM(EXTRACT(EPOCH FROM (r.hora_fin - r.hora_inicio)) / 3600.0), 0)
                                                         AS horas,
               COALESCE(SUM(r.monto_total), 0)             AS ingresos
          FROM reserva r
         WHERE {where}
         GROUP BY r.hora_inicio::time
         ORDER BY reservas DESC, horas DESC
        """,
        {
            "fi": fi, "ff": ff,
            "id_cancha": filtros["id_cancha"], "id_cliente": filtros["id_cliente"],
            "estado": filtros["estado"],
        },
    )
    for f in por_hora:
        f["hora"] = str(f["hora"])[:5]
        f["horas"] = _redondear(f["horas"])
        f["ingresos"] = _redondear(f["ingresos"])

    # Desglose por estado: de aquí salen las tasas.
    por_estado = _filas(
        f"""
        SELECT r.estado_reserva AS estado, COUNT(*) AS reservas
          FROM reserva r
         WHERE {where}
         GROUP BY r.estado_reserva
         ORDER BY reservas DESC
        """,
        {
            "fi": fi, "ff": ff,
            "id_cancha": filtros["id_cancha"], "id_cliente": filtros["id_cliente"],
            "estado": filtros["estado"],
        },
    )
    mapa_estado = {f["estado"]: f["reservas"] for f in por_estado}

    por_cancha = _filas(
        f"""
        SELECT c.id_cancha, c.nombre_cancha, c.tipo_deporte,
               COUNT(*)                          AS reservas,
               COUNT(*) FILTER (WHERE r.estado_reserva = ANY(:ocupan)) AS cobradas,
               COALESCE(SUM(r.monto_total), 0)   AS monto_comprometido
          FROM reserva r
          JOIN cancha c ON c.id_cancha = r.id_cancha
         WHERE {where}
         GROUP BY c.id_cancha, c.nombre_cancha, c.tipo_deporte
         ORDER BY reservas DESC
        """,
        {
            "fi": fi, "ff": ff, "ocupan": list(RESERVAS_QUE_OCUPAN),
            "id_cancha": filtros["id_cancha"], "id_cliente": filtros["id_cliente"],
            "estado": filtros["estado"],
        },
    )
    for f in por_cancha:
        f["monto_comprometido"] = _redondear(f["monto_comprometido"])
        f["tasa_conversion"] = _tasa(f["cobradas"], f["reservas"])

    total = sum(mapa_estado.values())
    duracion_promedio = _uno(
        f"""
        SELECT COALESCE(AVG(EXTRACT(EPOCH FROM (r.hora_fin - r.hora_inicio)) / 3600.0), 0)
          FROM reserva r WHERE {where}
        """,
        {
            "fi": fi, "ff": ff,
            "id_cancha": filtros["id_cancha"], "id_cliente": filtros["id_cliente"],
            "estado": filtros["estado"],
        },
    )
    monto_promedio = _uno(
        f"SELECT COALESCE(AVG(r.monto_total), 0) FROM reserva r WHERE {where}",
        {
            "fi": fi, "ff": ff,
            "id_cancha": filtros["id_cancha"], "id_cliente": filtros["id_cliente"],
            "estado": filtros["estado"],
        },
    )

    # Horario punta: el primero de por_hora ya viene ordenado por demanda.
    punta = por_hora[0] if por_hora else None

    metricas = {
        "total_reservas": total,
        "reservas_cobradas": mapa_estado.get("confirmada", 0)
        + mapa_estado.get("completada", 0),
        "tasa_cancelacion": _tasa(mapa_estado.get("cancelada", 0), total),
        "tasa_expiracion": _tasa(mapa_estado.get("expirada", 0), total),
        "duracion_promedio_horas": _redondear(duracion_promedio),
        "monto_promedio": _redondear(monto_promedio),
        "horario_mayor_demanda": punta["hora"] if punta else None,
        "reservas_horario_punta": punta["reservas"] if punta else 0,
        "dias_con_reservas": len(por_dia),
    }
    return {
        "detalle": {
            "por_dia": por_dia,
            "por_hora": por_hora,
            "por_estado": por_estado,
            "por_cancha": por_cancha,
        },
        "metricas": metricas,
    }


def _analisis_pagos(fi, ff, params):
    """Ingresos por método, neto de devoluciones, y ritmo de cobro."""
    filtros = {
        "metodo_pago": [str(m).strip() for m in (params.get("metodo_pago") or []) if str(m).strip()],
        "id_cancha": _lista_ids(params.get("id_cancha")),
    }

    cond = ["p.fecha_pago::date BETWEEN :fi AND :ff", "p.estado_pago = ANY(:estados)"]
    params_sql = {"fi": fi, "ff": ff, "estados": list(PAGOS_QUE_CUENTAN)}
    joins = ""
    if filtros["metodo_pago"]:
        cond.append("p.metodo_pago = ANY(:metodo)")
        params_sql["metodo"] = filtros["metodo_pago"]
    if filtros["id_cancha"]:
        joins = "JOIN reserva r ON r.id_reserva = p.id_reserva"
        cond.append("r.id_cancha = ANY(:id_cancha)")
        params_sql["id_cancha"] = filtros["id_cancha"]
    where = " AND ".join(cond)

    por_metodo = _filas(
        f"""
        SELECT p.metodo_pago                                   AS metodo_pago,
               COUNT(*)                                        AS cantidad,
               COALESCE(SUM(p.monto), 0)                      AS bruto,
               COALESCE(SUM(p.monto_devuelto), 0)             AS devuelto,
               COALESCE(SUM(p.monto), 0) - COALESCE(SUM(p.monto_devuelto), 0) AS neto
          FROM pago p
          {joins}
         WHERE {where}
         GROUP BY p.metodo_pago
         ORDER BY neto DESC
        """,
        params_sql,
    )
    for f in por_metodo:
        for campo in ("bruto", "devuelto", "neto"):
            f[campo] = _redondear(f[campo])

    por_dia = _filas(
        f"""
        SELECT p.fecha_pago::date AS fecha,
               COUNT(*)           AS cantidad,
               COALESCE(SUM(p.monto), 0) - COALESCE(SUM(p.monto_devuelto), 0) AS neto
          FROM pago p
          {joins}
         WHERE {where}
         GROUP BY p.fecha_pago::date
         ORDER BY 1
        """,
        params_sql,
    )
    for f in por_dia:
        f["neto"] = _redondear(f["neto"])

    por_cancha = _filas(
        f"""
        SELECT c.id_cancha, c.nombre_cancha,
               COUNT(*)                                        AS cantidad,
               COALESCE(SUM(p.monto), 0) - COALESCE(SUM(p.monto_devuelto), 0) AS neto
          FROM pago p
          JOIN reserva r ON r.id_reserva = p.id_reserva
          JOIN cancha  c ON c.id_cancha  = r.id_cancha
         WHERE {where}
         GROUP BY c.id_cancha, c.nombre_cancha
         ORDER BY neto DESC
        """,
        params_sql,
    )
    for f in por_cancha:
        f["neto"] = _redondear(f["neto"])

    # Estados de todos los pagos del rango, no solo los que cuentan como
    # ingreso: así se ve también la tasa de rechazo y de expiración.
    estados_rango = [dict(f) for f in _filas(
        """
        SELECT p.estado_pago AS estado, COUNT(*) AS cantidad
          FROM pago p
         WHERE p.fecha_pago::date BETWEEN :fi AND :ff
         GROUP BY p.estado_pago
         ORDER BY cantidad DESC
        """,
        {"fi": fi, "ff": ff},
    )]

    total_pagos = sum(f["cantidad"] for f in por_metodo)
    ingresos_brutos = sum(f["bruto"] for f in por_metodo)
    devoluciones = sum(f["devuelto"] for f in por_metodo)
    ingresos_netos = ingresos_brutos - devoluciones
    mapa_estado = {f["estado"]: f["cantidad"] for f in estados_rango}
    total_rango = sum(mapa_estado.values())

    ticket_promedio = (
        ingresos_netos / total_pagos if total_pagos else 0.0
    )

    metricas = {
        "total_pagos": total_pagos,
        "ingresos_brutos": _redondear(ingresos_brutos),
        "devoluciones": _redondear(devoluciones),
        # La regla del documento: ingresos = aprobados - devoluciones.
        "ingresos_netos": _redondear(ingresos_netos),
        "ticket_promedio": _redondear(ticket_promedio),
        "metodo_mayor_ingreso": por_metodo[0]["metodo_pago"] if por_metodo else None,
        "tasa_rechazo": _tasa(mapa_estado.get("rechazado", 0), total_rango),
        "tasa_expiracion_pago": _tasa(mapa_estado.get("expirado", 0), total_rango),
        "dias_con_pagos": len(por_dia),
    }
    return {
        "detalle": {
            "por_metodo": por_metodo,
            "por_dia": por_dia,
            "por_cancha": por_cancha,
            "por_estado": estados_rango,
        },
        "metricas": metricas,
    }


def _analisis_canchas(fi, ff, params):
    """Ocupación por cancha: la más rentable y la más ociosa."""
    solo_disponibles = bool(params.get("solo_disponibles"))

    cond_reserva = [
        "r.fecha_reserva BETWEEN :fi AND :ff",
        "r.estado_reserva = ANY(:ocupan)",
    ]
    if solo_disponibles:
        cond_reserva.append("c.estado = 'disponible'")
    where_r = " AND ".join(cond_reserva)
    params_sql = {"fi": fi, "ff": ff, "ocupan": list(RESERVAS_QUE_OCUPAN)}

    canchas = _filas(
        f"""
        SELECT c.id_cancha,
               c.nombre_cancha,
               c.tipo_deporte,
               c.precio_hora,
               c.estado,
               c.horario_apertura,
               c.horario_cierre,
               COALESCE(res.reservas, 0)          AS reservas,
               COALESCE(res.horas, 0)             AS horas_reservadas,
               COALESCE(res.monto, 0)             AS ingresos
          FROM cancha c
          LEFT JOIN (
                SELECT r.id_cancha,
                       COUNT(*)                        AS reservas,
                       COALESCE(SUM(EXTRACT(EPOCH FROM (r.hora_fin - r.hora_inicio)) / 3600.0), 0) AS horas,
                       COALESCE(SUM(r.monto_total), 0) AS monto
                  FROM reserva r
                 WHERE r.estado_reserva = ANY(:ocupan)
                   AND r.fecha_reserva BETWEEN :fi AND :ff
                 GROUP BY r.id_cancha
               ) res ON res.id_cancha = c.id_cancha
         WHERE (:solo = 0 OR c.estado = 'disponible')
         ORDER BY ingresos DESC, reservas DESC
        """,
        {**params_sql, "solo": 1 if solo_disponibles else 0},
    )

    # Días del rango: se cuenta solo lo que la cancha atiende. Si no tiene
    # horario configurado se cae a 06:00-23:00, que es lo que usa la UI.
    dias = (ff - fi).days + 1
    for f in canchas:
        f["horas_reservadas"] = _redondear(f["horas_reservadas"])
        f["ingresos"] = _redondear(f["ingresos"])
        f["precio_hora"] = _redondear(f["precio_hora"])
        f["horario_apertura"] = str(f["horario_apertura"])[:5] if f["horario_apertura"] else None
        f["horario_cierre"] = str(f["horario_cierre"])[:5] if f["horario_cierre"] else None

        if f["horario_apertura"] and f["horario_cierre"]:
            apertura = _a_horas(f["horario_apertura"])
            cierre = _a_horas(f["horario_cierre"])
            horas_dia = max(0.0, cierre - apertura)
        else:
            horas_dia = 17.0
        f["horas_disponibles_dia"] = _redondear(horas_dia)
        f["horas_disponibles"] = _redondear(horas_dia * dias)
        f["porcentaje_ocupacion"] = _tasa(f["horas_reservadas"], horas_dia * dias)
        f["ingreso_por_hora_reservada"] = _redondear(
            f["ingresos"] / f["horas_reservadas"] if f["horas_reservadas"] else 0
        )

    con_ocupacion = [f for f in canchas if f["horas_reservadas"] > 0]
    sin_ocupacion = [f for f in canchas if f["horas_reservadas"] == 0]
    detalle = {
        "canchas": canchas,
        "ranking_ocupacion": sorted(
            con_ocupacion, key=lambda x: x["porcentaje_ocupacion"], reverse=True
        )[:10],
        "mas_ociosas": sorted(sin_ocupacion, key=lambda x: x["nombre_cancha"])[:10],
    }
    metricas = {
        "total_canchas": len(canchas),
        "canchas_con_ocupacion": len(con_ocupacion),
        "canchas_sin_ocupacion": len(sin_ocupacion),
        "horas_reservadas": _redondear(sum(f["horas_reservadas"] for f in canchas)),
        "horas_disponibles": _redondear(sum(f["horas_disponibles"] for f in canchas)),
        "ocupacion_promedio": _tasa(
            sum(f["horas_reservadas"] for f in canchas),
            sum(f["horas_disponibles"] for f in canchas),
        ),
        "ingresos": _redondear(sum(f["ingresos"] for f in canchas)),
        "cancha_mayor_ocupacion": (
            detalle["ranking_ocupacion"][0]["nombre_cancha"]
            if detalle["ranking_ocupacion"] else None
        ),
        "cancha_mayor_ingreso": (
            max(canchas, key=lambda x: x["ingresos"])["nombre_cancha"]
            if canchas and any(f["ingresos"] > 0 for f in canchas) else None
        ),
    }
    return {"detalle": detalle, "metricas": metricas}


def _a_horas(texto):
    """'08:30' -> 8.5"""
    try:
        horas, _, minutos = str(texto).partition(":")
        return int(horas) + int(minutos or 0) / 60.0
    except (TypeError, ValueError):
        return 0.0


def _analisis_clientes(fi, ff, params):
    """Clientes frecuentes, gasto y concentración."""
    solo_activos = bool(params.get("solo_con_reservas"))

    # Con solo_con_reservas el JOIN tiene que ser INNER: poner el filtro en el ON
    # de un LEFT JOIN deja la fila del cliente sin reservas con r en NULL, asi
    # que el filtro no excluye a nadie.
    cond = ["r.fecha_reserva BETWEEN :fi AND :ff"]
    join_reserva = (
        "JOIN reserva r ON r.id_cliente = cl.id_cliente AND " + " AND ".join(cond)
        if solo_activos
        else "LEFT JOIN reserva r ON r.id_cliente = cl.id_cliente AND " + " AND ".join(cond)
    )
    params_sql = {"fi": fi, "ff": ff}

    clientes = _filas(
        f"""
        SELECT cl.id_cliente,
               per.nombre || ' ' || per.apellido AS nombre,
               per.email,
               COUNT(r.id_reserva) AS reservas,
               COUNT(r.id_reserva) FILTER (
                   WHERE r.estado_reserva = ANY(:cobradas)) AS reservas_cobradas,
               COUNT(r.id_reserva) FILTER (
                   WHERE r.estado_reserva = 'cancelada')  AS reservas_canceladas,
               COUNT(r.id_reserva) FILTER (
                   WHERE r.estado_reserva = 'expirada')   AS reservas_expiradas,
               COALESCE(SUM(r.monto_total) FILTER (
                   WHERE r.estado_reserva = ANY(:cobradas)), 0) AS gastado,
               COALESCE(SUM(EXTRACT(EPOCH FROM (r.hora_fin - r.hora_inicio)) / 3600.0), 0)
                                                              AS horas_reservadas
          FROM cliente cl
          JOIN usuario u  ON u.id_usuario = cl.id_usuario
          JOIN persona per ON per.id_persona = u.id_persona
          {join_reserva}
         GROUP BY cl.id_cliente, per.nombre, per.apellido, per.email
         ORDER BY reservas DESC, gastado DESC
        """,
        {**params_sql, "cobradas": list(RESERVAS_COBRADAS)},
    )
    for f in clientes:
        f["gastado"] = _redondear(f["gastado"])
        f["horas_reservadas"] = _redondear(f["horas_reservadas"])
        f["tasa_cancelacion"] = _tasa(f["reservas_canceladas"], f["reservas"])
        f["ticket_promedio"] = _redondear(
            f["gastado"] / f["reservas_cobradas"] if f["reservas_cobradas"] else 0
        )

    con_reservas = [f for f in clientes if f["reservas"] > 0]
    sin_reservas = [f for f in clientes if f["reservas"] == 0]

    total_reservas = sum(f["reservas"] for f in clientes)
    total_gastado = sum(f["gastado"] for f in clientes)
    canceladas = sum(f["reservas_canceladas"] for f in clientes)

    # Concentración: qué porcentaje de las reservas concentran los 5 más
    # activos. Dice si la dependencia es de un solo cliente o está repartida.
    top5 = con_reservas[:5]
    reserv_top5 = sum(f["reservas"] for f in top5)

    metricas = {
        "total_clientes": len(clientes),
        "clientes_con_reservas": len(con_reservas),
        "clientes_sin_reservas": len(sin_reservas),
        "total_reservas": total_reservas,
        "total_gastado": _redondear(total_gastado),
        "ticket_promedio": _redondear(
            total_gastado / sum(f["reservas_cobradas"] for f in clientes)
            if sum(f["reservas_cobradas"] for f in clientes) else 0
        ),
        "tasa_cancelacion_clientes": _tasa(canceladas, total_reservas),
        "reservas_por_cliente_promedio": _redondear(
            total_reservas / len(con_reservas) if con_reservas else 0
        ),
        "concentracion_top5": _tasa(reserv_top5, total_reservas),
        "cliente_mas_frecuente": con_reservas[0]["nombre"] if con_reservas else None,
        "cliente_mayor_gasto": (
            max(con_reservas, key=lambda x: x["gastado"])["nombre"]
            if con_reservas and any(f["gastado"] > 0 for f in con_reservas) else None
        ),
    }
    return {
        "detalle": {
            "clientes": clientes,
            "top_frecuentes": con_reservas[:10],
            "top_gasto": sorted(
                [f for f in con_reservas if f["gastado"] > 0],
                key=lambda x: x["gastado"],
                reverse=True,
            )[:10],
        },
        "metricas": metricas,
    }


MOTORES = {
    "reservas": _analisis_reservas,
    "pagos": _analisis_pagos,
    "canchas": _analisis_canchas,
    "clientes": _analisis_clientes,
}


# ---------------------------------------------------------------------
# Generar y persistir
# ---------------------------------------------------------------------
def calcular_analisis(tipo, fi, ff, parametros=None):
    """Solo calcula: devuelve detalle y métricas SIN tocar la base.

    Sirve para el comparativo, que necesita las métricas de un rango nuevo
    pero no quiere dejar un segundo análisis guardado.
    """
    if tipo not in MOTORES:
        raise ValueError(
            f"Tipo de análisis no válido. Use: {', '.join(TIPOS_ANALISIS)}."
        )
    return MOTORES[tipo](fi, ff, parametros or {})


def generar_analisis(tipo, fi, ff, parametros, id_administrador):
    """Calcula el análisis y lo GUARDA.

    Devuelve un dict con `guardado`: si es False no se persistió nada, que es
    lo que exige el documento cuando el rango no tiene datos.
    """
    if tipo not in MOTORES:
        raise ValueError(
            f"Tipo de análisis no válido. Use: {', '.join(TIPOS_ANALISIS)}."
        )
    if not id_administrador:
        raise ValueError("El análisis necesita un administrador responsable.")

    calculo = calcular_analisis(tipo, fi, ff, parametros)
    detalle = calculo["detalle"]
    metricas = calculo["metricas"]

    # El detalle se guarda siempre como listas para que el listado y la
    # exportación tengan la misma forma aunque el tipo no traiga filas.
    total_registros = _contar_registros(tipo, detalle)
    vacio = total_registros == 0

    if vacio:
        # Sin datos: avisa y NO guarda. Las métricas se devuelven vacías, no en
        # cero, para que quien consuma la API no confunda "no hay datos" con
        # "se midio y dio cero".
        return {
            "guardado": False,
            "mensaje": "sin datos",
            "tipo_analisis": tipo,
            "fecha_inicio": fi.isoformat(),
            "fecha_fin": ff.isoformat(),
            "parametros": parametros or {},
            "metricas": None,
            "total_registros": 0,
        }

    registro = AnalisisGenerado(
        tipo_analisis=tipo,
        fecha_inicio=fi,
        fecha_fin=ff,
        parametros=parametros or {},
        resultado=detalle,
        metricas=metricas,
        total_registros=total_registros,
        id_administrador=id_administrador,
    )
    db.session.add(registro)
    db.session.commit()

    return {
        "guardado": True,
        "mensaje": "Análisis generado y guardado.",
        "analisis": registro.to_dict(con_detalle=True),
    }


def _contar_registros(tipo, detalle):
    """De qué lista se cuentan las filas, según el tipo de análisis.

    Para canchas y clientes la lista base incluye todas las canchas o todos los
    clientes registrados, así que por sí sola no dice que haya datos. Si se
    contou eso, un rango vacío se guardaría como si tuviera contenido, y el
    documento pide no guardar nada cuando el rango no tiene datos. Por eso se
    cuentan solo las filas con actividad real dentro del rango.
    """
    listas = {
        "reservas": ("por_dia", None),
        "pagos": ("por_metodo", None),
        "canchas": ("canchas", "horas_reservadas"),
        "clientes": ("clientes", "reservas"),
    }
    config = listas.get(tipo)
    if not config:
        return 0
    clave, columna_actividad = config
    filas = detalle.get(clave) or []
    if not columna_actividad:
        return len(filas)
    return sum(1 for f in filas if (f.get(columna_actividad) or 0) > 0)


# ---------------------------------------------------------------------
# Consulta de los análisis guardados
# ---------------------------------------------------------------------
def listar_analisis(tipo_analisis=None, desde=None, hasta=None, limite=100):
    consulta = AnalisisGenerado.query
    if tipo_analisis:
        consulta = consulta.filter(AnalisisGenerado.tipo_analisis == tipo_analisis)
    if desde:
        consulta = consulta.filter(AnalisisGenerado.fecha_generado >= desde)
    if hasta:
        # 'hasta' es una fecha: se lleva al final del día para no perder el día
        # que el usuario quiere incluir.
        consulta = consulta.filter(
            AnalisisGenerado.fecha_generado < _fin_del_dia(hasta)
        )
    return (
        consulta.order_by(AnalisisGenerado.fecha_generado.desc())
        .limit(limite)
        .all()
    )


def _fin_del_dia(valor):
    from datetime import datetime, time as _time

    if isinstance(valor, datetime):
        return valor
    return datetime.combine(valor, _time(23, 59, 59))


def obtener_analisis(id_analisis):
    registro = db.session.get(AnalisisGenerado, id_analisis)
    if not registro:
        raise ValueError("El análisis solicitado no existe.")
    return registro


def eliminar_analisis(id_analisis):
    registro = obtener_analisis(id_analisis)
    db.session.delete(registro)
    db.session.commit()
    return True


def resultado_legible(registro):
    """Devuelve (detalle, metricas) o lanza ValueError si el registro está dañado.

    Un registro corrupto no debe tumbar el sistema: el que llama decide qué
    mostrar. Aquí se detecta y se explica.
    """
    detalle = registro.resultado
    metricas = registro.metricas
    problemas = []

    if not isinstance(detalle, dict):
        problemas.append("el resultado no es un objeto válido")
    if not isinstance(metricas, dict):
        problemas.append("las métricas no son un objeto válido")

    if problemas:
        raise ValueError(
            f"El análisis #{registro.id_analisis} está incompleto o dañado "
            f"({'; '.join(problemas)})."
        )
    return detalle, metricas


def filas_para_exportar(tipo, detalle):
    """Aplana el detalle a una lista de diccionarios, para PDF o Excel.

    Los exportadores de reportes ya saben leer filas con esa forma, así que
    el análisis reutiliza el mismo formato en vez de duplicar el generador.
    """
    if tipo == "reservas":
        return [
            {
                "fecha": f.get("fecha"),
                "reservas": f.get("reservas"),
                "cobradas": f.get("reservas_cobradas"),
                "horas_solicitadas": f.get("horas_solicitadas"),
            }
            for f in detalle.get("por_dia", [])
        ]
    if tipo == "pagos":
        return [
            {
                "metodo_pago": f.get("metodo_pago"),
                "cantidad": f.get("cantidad"),
                "bruto": f.get("bruto"),
                "devuelto": f.get("devuelto"),
                "neto": f.get("neto"),
            }
            for f in detalle.get("por_metodo", [])
        ]
    if tipo == "canchas":
        return [
            {
                "nombre_cancha": f.get("nombre_cancha"),
                "tipo_deporte": f.get("tipo_deporte"),
                "reservas": f.get("reservas"),
                "horas_reservadas": f.get("horas_reservadas"),
                "horas_disponibles": f.get("horas_disponibles"),
                "porcentaje_ocupacion": f.get("porcentaje_ocupacion"),
                "ingresos": f.get("ingresos"),
            }
            for f in detalle.get("canchas", [])
        ]
    if tipo == "clientes":
        return [
            {
                "nombre": f.get("nombre"),
                "email": f.get("email"),
                "reservas": f.get("reservas"),
                "cobradas": f.get("reservas_cobradas"),
                "canceladas": f.get("reservas_canceladas"),
                "gastado": f.get("gastado"),
                "ticket_promedio": f.get("ticket_promedio"),
            }
            for f in detalle.get("clientes", [])
        ]
    raise ValueError(f"Tipo de análisis no válido: {tipo}")


TITULOS_ANALISIS = {
    "reservas": "Análisis de Reservas",
    "pagos": "Análisis de Pagos",
    "canchas": "Análisis de Canchas y Ocupación",
    "clientes": "Análisis de Clientes",
}


# ---------------------------------------------------------------------
# Dashboard (se conserva lo que ya existía)
# ---------------------------------------------------------------------
def resumen_analitico():
    """Agrupa las vistas analíticas en una sola respuesta para el dashboard."""
    return {
        "ganancias_mensuales": _filas(
            "SELECT mes, cantidad_pagados, ingresos, por_cobrar, reembolsos "
            "FROM vista_ganancias_mensuales ORDER BY mes"
        ),
        "empleados": _filas(
            "SELECT nombre_empleado, cargo, pagos_procesados, total_recaudado, por_cobrar "
            "FROM vista_analitica_empleados ORDER BY total_recaudado DESC"
        ),
        "top_canchas": _filas(
            "SELECT nombre_cancha, tipo_deporte, SUM(cantidad) AS reservas "
            "FROM vista_analitica_reservas "
            "WHERE estado_reserva <> 'cancelada' "
            "GROUP BY nombre_cancha, tipo_deporte ORDER BY reservas DESC"
        ),
        "saldos_clientes": _filas(
            "SELECT nombre_cliente, total_comprometido, total_pagado, saldo_pendiente "
            "FROM vista_saldos_clientes ORDER BY saldo_pendiente DESC"
        ),
        "pagos_por_metodo": _filas(
            "SELECT metodo_pago, SUM(monto_total) AS total, "
            "SUM(cantidad_pagos) AS cantidad "
            "FROM vista_analitica_pagos GROUP BY metodo_pago "
            "ORDER BY total DESC"
        ),
    }


def total_analisis_guardados():
    try:
        return db.session.execute(
            text("SELECT COUNT(*) FROM analisis_generado")
        ).scalar() or 0
    except SQLAlchemyError:
        # Si la tabla todavía no existe, el resumen del dashboard sigue
        # funcionando: no debe romperse por esto.
        return 0
