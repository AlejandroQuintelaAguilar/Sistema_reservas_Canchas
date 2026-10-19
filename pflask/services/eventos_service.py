from datetime import datetime, date
from extensions import db
from models.bloqueo import Bloqueo
from models.cancha import Cancha
from models.evento import Evento
from models.reserva import Reserva

ESTADOS_RESERVA_ACTIVOS = ("pendiente", "confirmada")
TIPOS_EVENTO_VALIDOS = ("Deportivo", "Social", "Servicio Social")
TIPO_EVENTO_PUBLICO = "Servicio Social"


class EventosService:
    @staticmethod
    def _verificar_cancha(id_cancha):
        """La cancha debe existir y estar disponible."""
        cancha = db.session.get(Cancha, id_cancha)
        if not cancha:
            raise ValueError(f"La cancha con ID {id_cancha} no existe.")
        if cancha.estado != "disponible":
            raise ValueError(
                f"La cancha '{cancha.nombre_cancha}' no está disponible "
                f"(estado actual: {cancha.estado})."
            )
        return cancha

    @staticmethod
    def _verificar_solape_reservas(id_cancha, fecha, inicio, fin):
        """Un evento no puede ocupar una cancha con reservas vigentes."""
        reservas = Reserva.query.filter(
            Reserva.id_cancha == id_cancha,
            Reserva.fecha_reserva == fecha,
            Reserva.estado_reserva.in_(ESTADOS_RESERVA_ACTIVOS),
        ).all()
        for r in reservas:
            if r.hora_fin > inicio and r.hora_inicio < fin:
                raise ValueError(
                    "La cancha ya tiene una reserva "
                    f"({r.hora_inicio.strftime('%H:%M')}-{r.hora_fin.strftime('%H:%M')}) "
                    "en ese horario. No se puede crear el evento."
                )

    @staticmethod
    def _verificar_solape_bloqueos(id_cancha, fecha, inicio, fin):
        """Un evento no puede ocupar una cancha bloqueada (activo, dentro del rango de fechas)."""
        bloqueos = Bloqueo.query.filter(
            Bloqueo.id_cancha == id_cancha,
            Bloqueo.estado == "activo",
            Bloqueo.fecha_inicio <= fecha,
            Bloqueo.fecha_fin >= fecha,
        ).all()
        for b in bloqueos:
            if b.hora_fin > inicio and b.hora_inicio < fin:
                raise ValueError(
                    "La cancha está bloqueada en ese horario "
                    f"({b.hora_inicio.strftime('%H:%M')}-{b.hora_fin.strftime('%H:%M')}, "
                    f"motivo: {b.motivo})."
                )

    @staticmethod
    def _verificar_solape_eventos(id_cancha, fecha, inicio, fin, excluir_id=None):
        """Un evento no puede solaparse con otro evento de la misma cancha."""
        consulta = Evento.query.filter(
            Evento.id_cancha == id_cancha,
            Evento.fecha_evento == fecha,
            Evento.hora_inicio < fin,
            Evento.hora_fin > inicio,
        )
        if excluir_id is not None:
            consulta = consulta.filter(Evento.id_evento != excluir_id)

        for e in consulta.all():
            raise ValueError(
                f"La cancha ya tiene el evento '{e.nombre_evento}' en ese horario "
                f"({e.hora_inicio.strftime('%H:%M')}-{e.hora_fin.strftime('%H:%M')})."
            )

    @staticmethod
    def _verificar_disponibilidad(id_cancha, fecha, inicio, fin, excluir_id=None):
        """Regla compartida: cancha disponible + sin bloqueos, reservas ni eventos."""
        EventosService._verificar_cancha(id_cancha)
        EventosService._verificar_solape_bloqueos(id_cancha, fecha, inicio, fin)
        EventosService._verificar_solape_reservas(id_cancha, fecha, inicio, fin)
        EventosService._verificar_solape_eventos(
            id_cancha, fecha, inicio, fin, excluir_id=excluir_id
        )

    @staticmethod
    def get_all_eventos(tipo=None, solo_vigentes=False):
        """Eventos ordenados por fecha.

        Con solo_vigentes=True se descartan los que ya terminaron: los que
        son de dias anteriores o los de hoy cuya hora_fin ya paso. El admin
        es el unico que ve el historial completo.
        """
        consulta = Evento.query
        if tipo:
            consulta = consulta.filter(Evento.tipo_evento == tipo)
        if solo_vigentes:
            ahora = datetime.now()
            consulta = consulta.filter(
                db.or_(
                    Evento.fecha_evento > ahora.date(),
                    db.and_(
                        Evento.fecha_evento == ahora.date(),
                        Evento.hora_fin > ahora.time(),
                    ),
                )
            )
        return consulta.order_by(
            Evento.fecha_evento.asc(), Evento.hora_inicio.asc()
        ).all()

    @staticmethod
    def get_evento_by_id(id_evento):
        return db.session.get(Evento, id_evento)

    @staticmethod
    def create_evento(data):
        fecha = datetime.strptime(data["fecha_evento"], "%Y-%m-%d").date()
        if fecha < date.today():
            raise ValueError("La fecha del evento no puede ser anterior a la fecha actual.")

        inicio = datetime.strptime(data["hora_inicio"], "%H:%M").time()
        fin = datetime.strptime(data["hora_fin"], "%H:%M").time()
        if fin <= inicio:
            raise ValueError("La hora de fin debe ser posterior a la hora de inicio.")

        EventosService._verificar_disponibilidad(data["id_cancha"], fecha, inicio, fin)

        nuevo_evento = Evento(
            nombre_evento=data["nombre_evento"],
            tipo_evento=data.get("tipo_evento"),
            fecha_evento=fecha,
            hora_inicio=inicio,
            hora_fin=fin,
            cupo_maximo=data.get("cupo_maximo"),
            organizador=data.get("organizador"),
            descripcion=data.get("descripcion"),
            id_cancha=data["id_cancha"]
        )

        db.session.add(nuevo_evento)
        db.session.commit()
        return nuevo_evento

    @staticmethod
    def update_evento(id_evento, data):
        evento = db.session.get(Evento, id_evento)
        if not evento:
            return None

        fecha = evento.fecha_evento
        if data.get("fecha_evento"):
            fecha = datetime.strptime(data["fecha_evento"], "%Y-%m-%d").date()
            if fecha < date.today():
                raise ValueError("La fecha del evento no puede ser anterior a la fecha actual.")

        inicio = evento.hora_inicio
        if "hora_inicio" in data and data["hora_inicio"]:
            inicio = datetime.strptime(data["hora_inicio"], "%H:%M").time()

        fin = evento.hora_fin
        if "hora_fin" in data and data["hora_fin"]:
            fin = datetime.strptime(data["hora_fin"], "%H:%M").time()

        if fin <= inicio:
            raise ValueError("La hora de fin debe ser posterior a la hora de inicio.")

        id_cancha = evento.id_cancha
        if "id_cancha" in data and data["id_cancha"] is not None:
            id_cancha = int(data["id_cancha"])

        # Revalida todo excluyendo el propio evento.
        EventosService._verificar_disponibilidad(
            id_cancha, fecha, inicio, fin, excluir_id=evento.id_evento
        )

        if "nombre_evento" in data and data["nombre_evento"]:
            evento.nombre_evento = data["nombre_evento"]
        if "tipo_evento" in data and data["tipo_evento"]:
            evento.tipo_evento = data["tipo_evento"]
        evento.fecha_evento = fecha
        evento.hora_inicio = inicio
        evento.hora_fin = fin
        if "cupo_maximo" in data:
            evento.cupo_maximo = (
                int(data["cupo_maximo"]) if data["cupo_maximo"] not in (None, "") else None
            )
        if "organizador" in data:
            evento.organizador = data["organizador"]
        if "descripcion" in data:
            evento.descripcion = data["descripcion"]
        evento.id_cancha = id_cancha

        db.session.commit()
        return evento

    @staticmethod
    def delete_evento(id_evento):
        evento = db.session.get(Evento, id_evento)
        if not evento:
            return False
        db.session.delete(evento)
        db.session.commit()
        return True
