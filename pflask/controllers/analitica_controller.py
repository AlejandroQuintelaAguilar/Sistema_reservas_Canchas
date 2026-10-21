from flask import Blueprint, g, jsonify, request, send_file

from extensions import db
from services import analitica_service
from services.auth_service import require_auth
from services.reportes_exporters import exportar_excel, exportar_pdf
from utils.responses import error_json
from validators.analitica_validator import (
    ESTADOS_RESERVA,
    METODOS_PAGO,
    validar_fechas,
    validar_generar,
    validar_listado,
)

analitica_bp = Blueprint("analitica", __name__, url_prefix="/api/analitica")


def _id_administrador_actual():
    """El análisis cuelga de administrador.id_administrador, no de usuario."""
    from models.administrador import Administrador

    usuario = getattr(g, "current_user", None)
    if usuario is None:
        return None
    fila = Administrador.query.filter_by(id_usuario=usuario.id_usuario).first()
    return fila.id_administrador if fila else None


# =====================================================================
# CATÁLOGO
# =====================================================================
@analitica_bp.get("/tipos")
@require_auth(roles=["administrador"])
def listar_tipos():
    """Qué tipos de análisis se pueden generar y qué filtros acepta cada uno."""
    parametros = {
        "reservas": ["id_cancha", "id_cliente", "estado"],
        "pagos": ["metodo_pago", "id_cancha"],
        "canchas": ["solo_disponibles"],
        "clientes": ["solo_con_reservas"],
    }
    return jsonify({
        "tipos": [
            {
                "valor": t,
                "etiqueta": analitica_service.ETIQUETA_TIPO[t],
                "parametros": parametros[t],
            }
            for t in analitica_service.TIPOS_ANALISIS
        ],
        "estados_reserva": list(ESTADOS_RESERVA),
        "metodos_pago": list(METODOS_PAGO),
    }), 200


# =====================================================================
# RESUMEN PARA EL DASHBOARD
# =====================================================================
@analitica_bp.get("")
@require_auth(roles=["administrador"])
def resumen():
    try:
        datos = analitica_service.resumen_analitico()
        datos["analisis_guardados"] = analitica_service.total_analisis_guardados()
        return jsonify(datos), 200
    except Exception as e:
        return error_json("Error interno al consultar la analítica.", str(e), 500)


# =====================================================================
# GENERAR ANÁLISIS (calcula y PERSISTE)
# =====================================================================
@analitica_bp.post("/analisis")
@require_auth(roles=["administrador"])
def generar_analisis():
    """Elige tipo + rango + parámetros, calcula las métricas y las guarda.

    Si el rango no tiene datos, avisa con "sin datos" y NO guarda nada.
    """
    try:
        datos = validar_generar(request.get_json(silent=True))
    except ValueError as e:
        return error_json(str(e), codigo=400)

    id_admin = _id_administrador_actual()
    if not id_admin:
        return error_json(
            "La sesión no corresponde a un administrador registrado.", codigo=403
        )

    try:
        resultado = analitica_service.generar_analisis(
            datos["tipo_analisis"],
            datos["fecha_inicio"],
            datos["fecha_fin"],
            datos["parametros"],
            id_admin,
        )
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e), codigo=400)
    except Exception as e:
        db.session.rollback()
        return error_json("Error interno al generar el análisis.", str(e), 500)

    if not resultado["guardado"]:
        # Sin datos: 200 con el aviso, para que el frontend lo muestre claro.
        return jsonify(resultado), 200
    return jsonify(resultado), 201


# =====================================================================
# CONSULTAR ESTADÍSTICA GUARDADA
# =====================================================================
@analitica_bp.get("/analisis")
@require_auth(roles=["administrador"])
def listar_analisis():
    """Lista los análisis guardados, con filtros por tipo y fecha."""
    try:
        filtros = validar_listado(request.args)
    except ValueError as e:
        return error_json(str(e), codigo=400)

    try:
        registros = analitica_service.listar_analisis(**filtros)
    except Exception as e:
        db.session.rollback()
        return error_json("Error interno al listar los análisis.", str(e), 500)

    # Un registro dañado no puede romper el listado: se marca y se sigue.
    elementos = []
    for registro in registros:
        item = registro.to_dict()
        try:
            analitica_service.resultado_legible(registro)
            item["estado"] = "ok"
        except ValueError as e:
            item["estado"] = "corrupto"
            item["error"] = str(e)
        elementos.append(item)

    return jsonify(elementos), 200


@analitica_bp.get("/analisis/<int:id_analisis>")
@require_auth(roles=["administrador"])
def obtener_analisis(id_analisis):
    """Detalle de un análisis guardado, con sus métricas y su detalle."""
    try:
        registro = analitica_service.obtener_analisis(id_analisis)
    except ValueError as e:
        return error_json(str(e), codigo=404)

    try:
        detalle, metricas = analitica_service.resultado_legible(registro)
    except ValueError as e:
        # Registro corrupto: se explica el problema y se manda el error, sin
        # una excepción sin manejar. El frontend vuelve al listado.
        return error_json(str(e), codigo=422)

    datos = registro.to_dict(con_detalle=True)
    datos["resultado"] = detalle
    datos["metricas"] = metricas
    datos["estado"] = "ok"
    return jsonify(datos), 200


@analitica_bp.delete("/analisis/<int:id_analisis>")
@require_auth(roles=["administrador"])
def eliminar_analisis(id_analisis):
    try:
        analitica_service.eliminar_analisis(id_analisis)
        return jsonify({"mensaje": "Análisis eliminado."}), 200
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e), codigo=404)
    except Exception as e:
        db.session.rollback()
        return error_json("Error interno al eliminar el análisis.", str(e), 500)


# =====================================================================
# EXPORTAR UN ANÁLISIS GUARDADO
# =====================================================================
@analitica_bp.get("/analisis/<int:id_analisis>/exportar")
@require_auth(roles=["administrador"])
def exportar_analisis(id_analisis):
    formato = (request.args.get("formato") or "excel").lower()
    if formato not in ("excel", "pdf"):
        return error_json("Formato no válido. Use: excel o pdf.", codigo=400)

    try:
        registro = analitica_service.obtener_analisis(id_analisis)
    except ValueError as e:
        return error_json(str(e), codigo=404)

    try:
        detalle, _ = analitica_service.resultado_legible(registro)
    except ValueError as e:
        return error_json(str(e), codigo=422)

    try:
        filas = analitica_service.filas_para_exportar(registro.tipo_analisis, detalle)
    except ValueError as e:
        return error_json(str(e), codigo=400)

    titulo = analitica_service.TITULOS_ANALISIS.get(
        registro.tipo_analisis, "Análisis"
    )
    fi = registro.fecha_inicio.isoformat()
    ff = registro.fecha_fin.isoformat()
    base = f"analisis_{registro.tipo_analisis}_{registro.id_analisis}_{fi}_{ff}"

    if formato == "excel":
        buffer = exportar_excel(
            registro.tipo_analisis, filas, fi, ff, titulo=titulo
        )
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"{base}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    buffer = exportar_pdf(registro.tipo_analisis, filas, fi, ff, titulo=titulo)
    return send_file(
        buffer, as_attachment=True, download_name=f"{base}.pdf", mimetype="application/pdf"
    )


# =====================================================================
# COMPARATIVO: UN ANÁLISIS NUEVO CONTRA UNO YA GUARDADO
# =====================================================================
@analitica_bp.get("/analisis/<int:id_analisis>/comparar")
@require_auth(roles=["administrador"])
def comparar_analisis(id_analisis):
    """Compara las métricas del análisis guardado contra otro rango.

    No persiste nada: es una lectura para ver la evolución.
    """
    try:
        referencia = analitica_service.obtener_analisis(id_analisis)
    except ValueError as e:
        return error_json(str(e), codigo=404)

    try:
        desde, hasta = validar_fechas(
            request.args.get("fecha_inicio"), request.args.get("fecha_fin")
        )
    except ValueError as e:
        return error_json(str(e), codigo=400)

    tipo = request.args.get("tipo_analisis") or referencia.tipo_analisis
    if tipo != referencia.tipo_analisis:
        return error_json(
            "Solo se puede comparar contra otro análisis del mismo tipo.",
            codigo=400,
        )

    try:
        detalle_ref, metricas_ref = analitica_service.resultado_legible(referencia)
        actual = analitica_service.calcular_analisis(
            tipo, desde, hasta, referencia.parametros or {}
        )
    except ValueError as e:
        db.session.rollback()
        return error_json(str(e), codigo=400)

    metricas_nuevas = actual.get("metricas") or {}
    detalle_nuevo = actual.get("detalle") or {}

    if not analitica_service._contar_registros(tipo, detalle_nuevo):
        # Sin datos en el rango nuevo: se responde igual, con la referencia,
        # para que la interfaz muestre el aviso sin romperse.
        return jsonify({
            "comparacion": False,
            "mensaje": "sin datos",
            "referencia": {
                "id_analisis": referencia.id_analisis,
                "fecha_inicio": referencia.fecha_inicio.isoformat(),
                "fecha_fin": referencia.fecha_fin.isoformat(),
                "metricas": metricas_ref,
            },
            "actual": {
                "fecha_inicio": desde.isoformat(),
                "fecha_fin": hasta.isoformat(),
                "metricas": metricas_nuevas,
            },
        }), 200

    diferencias = {}
    for clave, valor in (metricas_nuevas or {}).items():
        anterior = (metricas_ref or {}).get(clave)
        if isinstance(valor, (int, float)) and isinstance(anterior, (int, float)):
            diferencias[clave] = round(valor - anterior, 2)
        else:
            diferencias[clave] = None

    return jsonify({
        "comparacion": True,
        "referencia": {
            "id_analisis": referencia.id_analisis,
            "fecha_inicio": referencia.fecha_inicio.isoformat(),
            "fecha_fin": referencia.fecha_fin.isoformat(),
            "metricas": metricas_ref,
        },
        "actual": {
            "fecha_inicio": desde.isoformat(),
            "fecha_fin": hasta.isoformat(),
            "metricas": metricas_nuevas,
        },
        "diferencias": diferencias,
    }), 200
