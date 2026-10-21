from datetime import date, datetime

from services.analitica_service import ETIQUETA_TIPO, TIPOS_ANALISIS

# Estados de reserva válidos en la base.
ESTADOS_RESERVA = ("pendiente", "confirmada", "cancelada", "completada", "expirada")
METODOS_PAGO = ("efectivo", "tarjeta", "transferencia", "qr")


def _lista(valor):
    if valor in (None, "", []):
        return []
    if not isinstance(valor, (list, tuple)):
        return [valor]
    return [v for v in valor if v not in (None, "")]


def validar_fechas(fi, ff):
    """Regla 1 del documento: la fecha final no puede ser anterior a la inicial.

    Se hace aquí y además en el CHECK de la tabla, para que la regla no
    dependa de que la validación pase.
    """
    try:
        fecha_inicio = (
            datetime.strptime(fi, "%Y-%m-%d").date() if isinstance(fi, str) else fi
        )
        fecha_fin = datetime.strptime(ff, "%Y-%m-%d").date() if isinstance(ff, str) else ff
    except (TypeError, ValueError):
        raise ValueError("Formato de fecha inválido. Use AAAA-MM-DD")

    if not isinstance(fecha_inicio, date) or not isinstance(fecha_fin, date):
        raise ValueError("Debe indicar fecha_inicio y fecha_fin (AAAA-MM-DD)")

    if fecha_fin < fecha_inicio:
        raise ValueError("La fecha final no puede ser anterior a la inicial.")

    if (fecha_fin - fecha_inicio).days > 366:
        raise ValueError("El rango no puede superar los 366 días.")

    return fecha_inicio, fecha_fin


def validar_generar(data):
    """Valida el cuerpo de la petición de generación de análisis."""
    if not isinstance(data, dict):
        raise ValueError("Se esperaba un cuerpo JSON con los datos del análisis.")

    tipo = str(data.get("tipo_analisis") or data.get("tipo") or "").strip().lower()
    if tipo not in TIPOS_ANALISIS:
        raise ValueError(
            f"Tipo de análisis no válido. Use: {', '.join(TIPOS_ANALISIS)}."
        )

    fecha_inicio, fecha_fin = validar_fechas(
        data.get("fecha_inicio"), data.get("fecha_fin")
    )

    parametros = data.get("parametros") or {}
    if not isinstance(parametros, dict):
        raise ValueError("Los parámetros extra deben ser un objeto.")

    # Los parámetros extra solo se aceptan si tienen sentido para el tipo.
    permitidos = {
        "reservas": {"id_cancha", "id_cliente", "estado"},
        "pagos": {"metodo_pago", "id_cancha"},
        "canchas": {"solo_disponibles"},
        "clientes": {"solo_con_reservas"},
    }[tipo]
    desconocido = set(parametros) - permitidos
    if desconocido:
        raise ValueError(
            f"Parámetros no válidos para el análisis de {ETIQUETA_TIPO[tipo]}: "
            f"{', '.join(sorted(desconocido))}."
        )

    estados = [str(e).strip().lower() for e in _lista(parametros.get("estado"))]
    for estado in estados:
        if estado not in ESTADOS_RESERVA:
            raise ValueError(
                f"Estado de reserva inválido: {estado}. "
                f"Use: {', '.join(ESTADOS_RESERVA)}."
            )
    if estados:
        parametros["estado"] = estados

    metodos = [str(m).strip().lower() for m in _lista(parametros.get("metodo_pago"))]
    for metodo in metodos:
        if metodo not in METODOS_PAGO:
            raise ValueError(
                f"Método de pago inválido: {metodo}. Use: {', '.join(METODOS_PAGO)}."
            )
    if metodos:
        parametros["metodo_pago"] = metodos

    return {
        "tipo_analisis": tipo,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "parametros": parametros,
    }


def validar_listado(args):
    """Filtros del listado de análisis guardados."""
    tipo = (args.get("tipo_analisis") or "").strip().lower()
    if tipo and tipo not in TIPOS_ANALISIS:
        raise ValueError(
            f"Tipo de análisis no válido. Use: {', '.join(TIPOS_ANALISIS)}."
        )

    desde = hasta = None
    if args.get("desde"):
        desde = validar_fechas(args["desde"], args["desde"])[0]
    if args.get("hasta"):
        hasta = validar_fechas(args["hasta"], args["hasta"])[0]

    if desde and hasta and hasta < desde:
        raise ValueError("La fecha final no puede ser anterior a la inicial.")

    limite = args.get("limite") or 100
    try:
        limite = int(limite)
    except (TypeError, ValueError):
        raise ValueError("El límite debe ser un número entero.")
    if limite <= 0 or limite > 500:
        raise ValueError("El límite debe estar entre 1 y 500.")

    return {"tipo_analisis": tipo or None, "desde": desde, "hasta": hasta, "limite": limite}
