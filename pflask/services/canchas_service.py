from datetime import datetime

from extensions import db
from models.administrador import Administrador
from models.cancha import Cancha
from models.categoria import Categoria
from models.evento import Evento
from models.historial_estado_cancha import HistorialEstadoCancha
from models.historial_precio_cancha import HistorialPrecioCancha
from models.reserva import Reserva
from validators.cancha_validator import (
    convertir_precio,
    convertir_id_entero,
    convertir_bool,
    convertir_hora,
    validar_estado,
)

ESTADOS_VALIDOS = ("disponible", "mantenimiento", "fuera_servicio")


def obtener_categoria(id_categoria):
    categoria = db.session.get(Categoria, id_categoria)
    if not categoria:
        raise ValueError("La categoría indicada no existe.")
    return categoria


def obtener_administrador(id_administrador):
    administrador = db.session.get(Administrador, id_administrador)
    if not administrador:
        raise ValueError("El administrador indicado no existe.")
    return administrador


def listar_canchas(estado=None):
    query = Cancha.query
    if estado:
        estado = validar_estado(estado)
        query = query.filter_by(estado=estado)
    return query.order_by(Cancha.id_cancha.asc()).all()


def obtener_cancha_por_id(id_cancha):
    cancha = db.session.get(Cancha, id_cancha)
    if not cancha:
        raise ValueError("La cancha no existe.")
    return cancha


def registrar_cambio_estado(cancha, nuevo_estado, motivo=None, id_usuario=None):
    anterior = cancha.estado
    if anterior == nuevo_estado:
        return
    db.session.add(
        HistorialEstadoCancha(
            id_cancha=cancha.id_cancha,
            estado_anterior=anterior,
            estado_nuevo=nuevo_estado,
            motivo=(motivo or "").strip()[:300] or None,
            id_usuario=id_usuario,
            fecha=datetime.now(),
        )
    )


def registrar_cambio_precio(cancha, nuevo_precio, id_usuario=None):
    anterior = float(cancha.precio_hora)
    nuevo = float(nuevo_precio)
    if anterior == nuevo:
        return
    db.session.add(
        HistorialPrecioCancha(
            id_cancha=cancha.id_cancha,
            precio_anterior=anterior,
            precio_nuevo=nuevo,
            id_usuario=id_usuario,
            fecha=datetime.now(),
        )
    )


def crear_cancha(datos_texto, datos_crudos):
    precio = convertir_precio(datos_crudos.get("precio_hora"))
    id_categoria = convertir_id_entero(datos_crudos.get("id_categoria"), "id_categoria")
    id_administrador = convertir_id_entero(
        datos_crudos.get("id_administrador"), "id_administrador"
    )

    obtener_categoria(id_categoria)
    obtener_administrador(id_administrador)

    # El estado inicial SIEMPRE es DISPONIBLE según la lógica de negocio.
    estado = "disponible"
    techada = convertir_bool(datos_crudos.get("techada", False))

    nueva = Cancha(
        nombre_cancha=datos_texto["nombre_cancha"],
        tipo_deporte=datos_texto["tipo_deporte"],
        precio_hora=precio,
        ubicacion=datos_texto.get("ubicacion"),
        estado=estado,
        techada=techada,
        superficie=datos_texto.get("superficie"),
        imagen_url=(datos_crudos.get("imagen_url") or None),
        horario_apertura=convertir_hora(datos_crudos.get("horario_apertura")),
        horario_cierre=convertir_hora(datos_crudos.get("horario_cierre")),
        dias_atencion=(datos_crudos.get("dias_atencion") or None),
        id_categoria=id_categoria,
        id_administrador=id_administrador,
    )
    db.session.add(nueva)
    db.session.commit()
    return nueva


def consultar_disponibilidad(id_cancha, fecha, duracion):
    """Slots libres de la cancha (import diferido para evitar ciclo)."""
    from services.reservas_service import consultar_disponibilidad as _consultar

    return _consultar(id_cancha, fecha, duracion)


def modificar_cancha(id_cancha, datos_texto, datos_crudos, id_usuario=None):
    cancha = obtener_cancha_por_id(id_cancha)

    for campo in ("nombre_cancha", "tipo_deporte", "ubicacion", "superficie"):
        if campo in datos_texto:
            setattr(cancha, campo, datos_texto[campo])

    if "precio_hora" in datos_crudos:
        nuevo_precio = convertir_precio(datos_crudos["precio_hora"])
        registrar_cambio_precio(cancha, nuevo_precio, id_usuario)
        cancha.precio_hora = nuevo_precio

    if "techada" in datos_crudos:
        cancha.techada = convertir_bool(datos_crudos["techada"])

    if "imagen_url" in datos_crudos:
        imagen = datos_crudos["imagen_url"]
        cancha.imagen_url = (imagen.strip() or None) if isinstance(imagen, str) else None

    if "horario_apertura" in datos_crudos:
        cancha.horario_apertura = convertir_hora(
            datos_crudos["horario_apertura"], "horario_apertura"
        )
    if "horario_cierre" in datos_crudos:
        cancha.horario_cierre = convertir_hora(
            datos_crudos["horario_cierre"], "horario_cierre"
        )
    if "dias_atencion" in datos_crudos:
        dias = datos_crudos["dias_atencion"]
        cancha.dias_atencion = (dias.strip() or None) if isinstance(dias, str) else None

    if cancha.horario_apertura and cancha.horario_cierre:
        if cancha.horario_cierre <= cancha.horario_apertura:
            raise ValueError("El horario de cierre debe ser posterior al de apertura.")

    if "estado" in datos_crudos:
        nuevo_estado = validar_estado(datos_crudos["estado"])
        registrar_cambio_estado(
            cancha, nuevo_estado, datos_crudos.get("motivo"), id_usuario
        )
        cancha.estado = nuevo_estado

    if "id_categoria" in datos_crudos:
        id_categoria = convertir_id_entero(datos_crudos["id_categoria"], "id_categoria")
        obtener_categoria(id_categoria)
        cancha.id_categoria = id_categoria

    if "id_administrador" in datos_crudos:
        id_administrador = convertir_id_entero(
            datos_crudos["id_administrador"], "id_administrador"
        )
        obtener_administrador(id_administrador)
        cancha.id_administrador = id_administrador

    db.session.commit()
    return cancha


def eliminar_cancha(id_cancha):
    cancha = obtener_cancha_por_id(id_cancha)

    # Solo se puede eliminar físicamente si NO tiene reservas (ninguna) ni eventos.
    if Reserva.query.filter_by(id_cancha=id_cancha).count() > 0:
        raise ValueError(
            "La cancha tiene reservas asociadas. No se puede eliminar; "
            "márcala como fuera_servicio."
        )
    if Evento.query.filter_by(id_cancha=id_cancha).count() > 0:
        raise ValueError(
            "La cancha tiene eventos asociados. No se puede eliminar; "
            "márcala como fuera_servicio."
        )

    db.session.delete(cancha)
    db.session.commit()


def cambiar_estado_cancha(id_cancha, nuevo_estado, motivo=None, id_usuario=None):
    cancha = obtener_cancha_por_id(id_cancha)
    nuevo_estado = validar_estado(nuevo_estado)
    registrar_cambio_estado(cancha, nuevo_estado, motivo, id_usuario)
    cancha.estado = nuevo_estado
    db.session.commit()
    return cancha