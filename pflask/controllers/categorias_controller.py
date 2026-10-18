from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from extensions import db
from services import categorias_service
from services.auth_service import require_auth
from validators.categoria_validator import validar_datos_categoria
from utils.responses import error_json

categorias_bp = Blueprint("categorias", __name__, url_prefix="/api/categorias")


@categorias_bp.post("")
@require_auth(roles=["administrador"])
def crear_categoria():
    data = request.get_json(silent=True)

    try:
        datos = validar_datos_categoria(data)
        categoria = categorias_service.crear_categoria(datos)

        return jsonify({
            "mensaje": "Categoría creada con éxito.",
            "categoria": categoria.to_dict(),
        }), 201

    except ValueError as e:
        db.session.rollback()
        codigo = 409 if "ya existe" in str(e).lower() else 400
        return error_json(str(e), codigo=codigo)

    except IntegrityError:
        db.session.rollback()
        return error_json(
            "No se pudo crear la categoría porque el nombre ya existe.", codigo=409
        )

    except Exception as e:
        db.session.rollback()
        return error_json("Error interno al crear la categoría.", str(e), 500)


@categorias_bp.get("")
def obtener_categorias():
    try:
        categorias = categorias_service.listar_categorias()
        return jsonify([c.to_dict() for c in categorias]), 200
    except Exception as e:
        return error_json("Error interno al obtener categorías.", str(e), 500)


@categorias_bp.get("/<int:id_categoria>")
def obtener_categoria(id_categoria):
    if id_categoria <= 0:
        return error_json("El id_categoria debe ser mayor que 0.")

    try:
        categoria = categorias_service.obtener_categoria_por_id(id_categoria)
        return jsonify(categoria.to_dict()), 200
    except ValueError as e:
        return error_json(str(e), codigo=404)


@categorias_bp.patch("/<int:id_categoria>")
@require_auth(roles=["administrador"])
def modificar_categoria(id_categoria):
    if id_categoria <= 0:
        return error_json("El id_categoria debe ser mayor que 0.")

    data = request.get_json(silent=True)

    try:
        datos = validar_datos_categoria(data, parcial=True)
        categoria = categorias_service.modificar_categoria(id_categoria, datos)

        return jsonify({
            "mensaje": "Categoría modificada con éxito.",
            "categoria": categoria.to_dict(),
        }), 200

    except ValueError as e:
        db.session.rollback()
        mensaje = str(e)
        if "no existe" in mensaje.lower():
            return error_json(mensaje, codigo=404)
        if "ya existe" in mensaje.lower():
            return error_json(mensaje, codigo=409)
        return error_json(mensaje)

    except IntegrityError:
        db.session.rollback()
        return error_json("No se pudo modificar la categoría.", codigo=409)

    except Exception as e:
        db.session.rollback()
        return error_json("Error interno al modificar la categoría.", str(e), 500)


@categorias_bp.delete("/<int:id_categoria>")
@require_auth(roles=["administrador"])
def eliminar_categoria(id_categoria):
    if id_categoria <= 0:
        return error_json("El id_categoria debe ser mayor que 0.")

    try:
        categorias_service.eliminar_categoria(id_categoria)
        return jsonify({"mensaje": "Categoría eliminada con éxito."}), 200

    except ValueError as e:
        db.session.rollback()
        mensaje = str(e)
        if "no existe" in mensaje.lower():
            return error_json(mensaje, codigo=404)
        return error_json(mensaje, codigo=409)

    except Exception as e:
        db.session.rollback()
        return error_json("No se pudo eliminar la categoría.", str(e), 409)
