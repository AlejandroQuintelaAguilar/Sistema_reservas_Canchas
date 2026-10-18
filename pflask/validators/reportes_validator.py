from datetime import date

# Catalogo unico: son los tres tipos que el servicio sabe generar. Antes el
# validator aceptaba "canchas", "usuarios" y "eventos", que no se podian generar.
TIPOS_REPORTE = {
    "reservas",
    "ocupacion",
    "ingresos",
}


def validar_datos_reporte(data, parcial=False):
    if not isinstance(data, dict):
        raise ValueError("El cuerpo de la solicitud debe ser un objeto JSON válido.")

    if not data:
        raise ValueError("El cuerpo de la solicitud no puede estar vacío.")

    resultado = {}

    if not parcial or "tipo" in data:
        tipo = data.get("tipo")
        if not isinstance(tipo, str) or not tipo.strip():
            raise ValueError("tipo es obligatorio.")
        tipo = tipo.strip().lower()
        if tipo not in TIPOS_REPORTE:
            raise ValueError(
                "Tipo no válido. Use: reservas, ocupacion o ingresos."
            )
        resultado["tipo"] = tipo

    if "fecha_generado" in data:
        valor = data.get("fecha_generado")
        if not isinstance(valor, str) or not valor.strip():
            raise ValueError("fecha_generado debe tener formato AAAA-MM-DD.")
        try:
            resultado["fecha_generado"] = date.fromisoformat(valor.strip())
        except ValueError:
            raise ValueError("fecha_generado debe tener formato AAAA-MM-DD.")

    if "descripcion" in data:
        descripcion = data.get("descripcion")
        if descripcion is not None and not isinstance(descripcion, str):
            raise ValueError("La descripción debe ser un texto válido o null.")
        resultado["descripcion"] = (
            descripcion.strip() if descripcion and descripcion.strip() else None
        )

    if "id_administrador" in data:
        valor = data.get("id_administrador")
        if isinstance(valor, bool) or not isinstance(valor, int):
            raise ValueError("id_administrador debe ser un número entero.")
        if valor <= 0:
            raise ValueError("id_administrador debe ser mayor que 0.")
        resultado["id_administrador"] = valor

    if not parcial and "fecha_generado" not in resultado:
        resultado["fecha_generado"] = date.today()

    return resultado