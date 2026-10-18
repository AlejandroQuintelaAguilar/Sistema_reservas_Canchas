from datetime import datetime

from flask import Blueprint, g, jsonify, request, send_file
from sqlalchemy.exc import IntegrityError

from extensions import db
from services import reportes_service
from services.reportes_exporters import exportar_excel, exportar_pdf
from services.auth_service import require_auth
from utils.responses import error_json
from validators.reportes_validator import validar_datos_reporte

reportes_bp = Blueprint("reportes", __name__, url_prefix="/api/reportes")


def _parsear_fechas():
    fi = request.args.get("fecha_inicio")
    ff = request.args.get("fecha_fin")
    if not fi or not ff:
        raise ValueError("Debe indicar fecha_inicio y fecha_fin (AAAA-MM-DD)")
    try:
        fi_dt = datetime.strptime(fi, "%Y-%m-%d").date()
        ff_dt = datetime.strptime(ff, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("Formato de fecha inválido. Use AAAA-MM-DD")
    return fi_dt, ff_dt


def _parsear_filtros():
    """Filtros opcionales: cancha, cliente y estado."""
    return {
        "id_cancha": request.args.get("id_cancha"),
        "id_cliente": request.args.get("id_cliente"),
        "estado": request.args.get("estado"),
    }


def _id_administrador_actual():
    """El reporte cuelga de administrador.id_administrador, no de usuario.

    Los dos id no son el mismo numero: cada administrador tiene su id_usuario y
    su propio id_administrador, asi que hay que traducir de uno a otro.
    """
    from models.administrador import Administrador

    usuario = getattr(g, "current_user", None)
    if usuario is None:
        return None
    fila = Administrador.query.filter_by(id_usuario=usuario.id_usuario).first()
    return fila.id_administrador if fila else None


def _filtros_texto(filtros):
    partes = []
    if filtros.get("id_cancha"):
        partes.append(f"cancha={filtros['id_cancha']}")
    if filtros.get("id_cliente"):
        partes.append(f"cliente={filtros['id_cliente']}")
    if filtros.get("estado"):
        partes.append(f"estado={filtros['estado']}")
    return ", ".join(partes)


# =====================================================================
# REPORTES GENERADOS (consultas + exportación PDF/Excel)
# =====================================================================
@reportes_bp.get("/datos/<tipo>")
@require_auth(roles=["administrador"])
def obtener_reporte_datos(tipo):
    if tipo not in reportes_service.REPORTES:
        return error_json("Tipo de reporte no válido. Use: reservas, ocupacion o ingresos.", codigo=400)
    try:
        fi, ff = _parsear_fechas()
        filtros = _parsear_filtros()
        filas = reportes_service.REPORTES[tipo](fi, ff, filtros)

        if not filas:
            return jsonify({
                "tipo": tipo,
                "fecha_inicio": fi.isoformat(),
                "fecha_fin": ff.isoformat(),
                "mensaje": "sin datos",
                "total_registros": 0,
                "filas": [],
            }), 200

        # Cada generación deja rastro, como pide el documento.
        filtros_txt = _filtros_texto(filtros)
        reportes_service.registrar_generacion(
            tipo,
            _id_administrador_actual(),
            f"{fi.isoformat()} a {ff.isoformat()}"
            + (f" | {filtros_txt}" if filtros_txt else ""),
        )

        return jsonify({
            "tipo": tipo,
            "fecha_inicio": fi.isoformat(),
            "fecha_fin": ff.isoformat(),
            "filtros": filtros_txt or "sin filtro",
            "mensaje": f"{len(filas)} registro(s) encontrado(s)",
            "total_registros": len(filas),
            "filas": filas,
        }), 200
    except ValueError as e:
        return error_json(str(e), codigo=400)
    except Exception as e:
        db.session.rollback()
        return error_json("Error interno al generar el reporte.", str(e), 500)


@reportes_bp.get("/exportar/<tipo>")
@require_auth(roles=["administrador"])
def exportar_reporte(tipo):
    if tipo not in reportes_service.REPORTES:
        return error_json("Tipo de reporte no válido. Use: reservas, ocupacion o ingresos.", codigo=400)

    formato = request.args.get("formato", "pdf").lower()
    if formato not in ("pdf", "excel"):
        return error_json("Formato no válido. Use: pdf o excel.", codigo=400)

    try:
        fi, ff = _parsear_fechas()
        filtros = _parsear_filtros()
        filas = reportes_service.REPORTES[tipo](fi, ff, filtros)

        if not filas:
            return error_json("sin datos", codigo=404)

        filtros_txt = _filtros_texto(filtros)
        reportes_service.registrar_generacion(
            tipo,
            _id_administrador_actual(),
            f"exportacion {formato} | {fi.isoformat()} a {ff.isoformat()}"
            + (f" | {filtros_txt}" if filtros_txt else ""),
        )

        sufijo = f"_{filtros_txt.replace('=', '').replace(', ', '_')}" if filtros_txt else ""
        if formato == "excel":
            buffer = exportar_excel(tipo, filas, fi.isoformat(), ff.isoformat())
            return send_file(
                buffer,
                as_attachment=True,
                download_name=f"reporte_{tipo}_{fi}_{ff}{sufijo}.xlsx",
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        buffer = exportar_pdf(tipo, filas, fi.isoformat(), ff.isoformat())
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"reporte_{tipo}_{fi}_{ff}{sufijo}.pdf",
            mimetype="application/pdf",
        )
    except ValueError as e:
        return error_json(str(e), codigo=400)
    except Exception as e:
        db.session.rollback()
        return error_json("Error interno al exportar el reporte.", str(e), 500)


@reportes_bp.get("/tipos")
@require_auth(roles=["administrador"])
def listar_tipos():
    return jsonify({
        "tipos": list(reportes_service.TIPOS_REPORTE),
        "estados": [
            {
                "valor": estado,
                "etiqueta": reportes_service.ETIQUETA_ESTADO[estado],
            }
            for estado in reportes_service.ESTADOS_REPORTE
        ],
    }), 200


# =====================================================================
# CRUD DE LA TABLA reporte
# =====================================================================
@reportes_bp.post("")
@require_auth(roles=["administrador"])
def generar_reporte():
    data = request.get_json(silent=True)

    try:
        datos = validar_datos_reporte(data)

        # El dueño del reporte sale de la sesion, nunca del cuerpo del request:
        # la columna es NOT NULL y ademas no se debe dejar que el cliente
        # elija a nombre de que administrador se guarda.
        if "id_administrador" in datos:
            raise ValueError(
                "El id_administrador se toma de la sesión, no se envía en el cuerpo."
            )
        id_admin = _id_administrador_actual()
        if not id_admin:
            return error_json(
                "La sesión no corresponde a un administrador registrado.",
                codigo=403,
            )
        datos["id_administrador"] = id_admin

        reporte = reportes_service.generar_reporte(datos)

        return jsonify({
            "mensaje": "Reporte generado con éxito.",
            "reporte": reporte.to_dict(),
        }), 201

    except ValueError as e:
        db.session.rollback()
        return error_json("Datos inválidos.", str(e), codigo=400)

    except IntegrityError as e:
        db.session.rollback()
        return error_json("No se pudo generar el reporte.", str(e.orig), codigo=409)

    except Exception as e:
        db.session.rollback()
        return error_json("Error interno al generar el reporte.", str(e), 500)


@reportes_bp.get("")
@require_auth(roles=["administrador"])
def obtener_reportes():
    try:
        reportes = reportes_service.listar_reportes()
        return jsonify([r.to_dict() for r in reportes]), 200
    except Exception as e:
        db.session.rollback()
        return error_json("Error interno al obtener reportes.", str(e), 500)


@reportes_bp.get("/<int:id_reporte>")
@require_auth(roles=["administrador"])
def obtener_reporte(id_reporte):
    try:
        if id_reporte <= 0:
            return error_json("El id_reporte debe ser mayor que 0.", codigo=400)
        reporte = reportes_service.obtener_reporte_por_id(id_reporte)
        return jsonify(reporte.to_dict()), 200
    except ValueError as e:
        return error_json(str(e), codigo=404)
    except Exception as e:
        db.session.rollback()
        return error_json("Error interno al obtener el reporte.", str(e), 500)


@reportes_bp.delete("/<int:id_reporte>")
@require_auth(roles=["administrador"])
def eliminar_reporte(id_reporte):
    try:
        if id_reporte <= 0:
            return error_json("El id_reporte debe ser mayor que 0.", codigo=400)
        reportes_service.eliminar_reporte(id_reporte)
        return jsonify({"mensaje": "Reporte eliminado con éxito."}), 200

    except ValueError as e:
        db.session.rollback()
        return error_json(str(e), codigo=404)

    except Exception as e:
        db.session.rollback()
        return error_json("No se pudo eliminar el reporte.", str(e), 409)
