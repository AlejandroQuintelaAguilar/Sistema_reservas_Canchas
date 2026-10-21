"""Validaciones de forma del pago.

Las reglas de negocio (saldo, idempotencia, estados permitidos para aprobar,
rechazar o devolver) viven en services/pagos_service.py; aquí solo se revisa
el formato de los datos que llegan por la API.
"""

from datetime import datetime

from models.pago import ESTADOS_PAGO, ETIQUETA_ESTADO, METODOS_PAGO_VALIDOS

ESTADOS_PAGO_ETIQUETAS = ", ".join(
    f"{e} ({ETIQUETA_ESTADO[e]})" for e in ESTADOS_PAGO
)


def _validar_fecha(valor):
    if not isinstance(valor, str) or not valor.strip():
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(valor.strip().replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("fecha_pago debe tener formato AAAA-MM-DD o AAAA-MM-DDTHH:MM:SS.")


def _validar_id(valor, nombre, opcional=False):
    if valor is None or valor == "":
        if opcional:
            return None
        raise ValueError(f"{nombre} es obligatorio.")
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ValueError(f"{nombre} debe ser un número entero.")
    if valor <= 0:
        raise ValueError(f"{nombre} debe ser mayor que 0.")
    return valor


def validar_datos_pago(data, parcial=False):
    if not isinstance(data, dict):
        raise ValueError("El cuerpo de la solicitud debe ser un objeto JSON válido.")

    if not data:
        raise ValueError("El cuerpo de la solicitud no puede estar vacío.")

    resultado = {}

    if not parcial or "metodo_pago" in data:
        metodo = data.get("metodo_pago")
        if not isinstance(metodo, str) or not metodo.strip():
            raise ValueError("metodo_pago es obligatorio.")
        if len(metodo.strip()) > 50:
            raise ValueError("metodo_pago no puede superar 50 caracteres.")
        if metodo.strip().lower() not in METODOS_PAGO_VALIDOS:
            raise ValueError(
                "Método de pago no válido. Use: "
                + ", ".join(METODOS_PAGO_VALIDOS)
                + "."
            )
        resultado["metodo_pago"] = metodo.strip().lower()

    if "comprobante" in data:
        comprobante = data.get("comprobante")
        if comprobante is not None and not isinstance(comprobante, str):
            raise ValueError("El comprobante debe ser un texto válido o null.")
        resultado["comprobante"] = (
            comprobante.strip() if comprobante and comprobante.strip() else None
        )

    if "estado_pago" in data:
        estado = data.get("estado_pago")
        if not isinstance(estado, str):
            raise ValueError("estado_pago debe ser un texto válido.")
        estado = estado.strip().lower()
        if estado not in ESTADOS_PAGO:
            raise ValueError(f"Estado no válido. Use: {ESTADOS_PAGO_ETIQUETAS}.")
        resultado["estado_pago"] = estado

    if not parcial or "monto" in data:
        if isinstance(data.get("monto"), bool) or not isinstance(data.get("monto"), (int, float)):
            raise ValueError("monto debe ser un número.")
        if data["monto"] <= 0:
            raise ValueError("monto debe ser mayor que 0.")
        resultado["monto"] = data["monto"]

    if "fecha_pago" in data:
        resultado["fecha_pago"] = _validar_fecha(data.get("fecha_pago"))
    elif not parcial:
        resultado["fecha_pago"] = datetime.utcnow()

    if not parcial or "id_reserva" in data:
        resultado["id_reserva"] = _validar_id(data.get("id_reserva"), "id_reserva")

    if "id_empleado" in data:
        resultado["id_empleado"] = _validar_id(
            data.get("id_empleado"), "id_empleado", opcional=True
        )

    return resultado


def validar_estado_pago(estado):
    if not isinstance(estado, str):
        raise ValueError("estado_pago debe ser un texto válido.")
    estado = estado.strip().lower()
    if estado not in ESTADOS_PAGO:
        raise ValueError(f"Estado no válido. Use: {ESTADOS_PAGO_ETIQUETAS}.")
    return estado