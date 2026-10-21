from datetime import datetime

from extensions import db
from models.plantilla_notificacion import CANALES, TIPOS_PLANTILLA

ESTADOS_NOTIFICACION = ("pendiente", "enviado", "fallido")
MAX_INTENTOS_POR_DEFECTO = 3


class Notificacion(db.Model):
    __tablename__ = "notificacion"

    id_notificacion = db.Column(db.Integer, primary_key=True)
    id_plantilla = db.Column(
        db.Integer,
        db.ForeignKey("plantilla_notificacion.id_plantilla", onupdate="CASCADE", ondelete="SET NULL"),
    )
    id_reserva = db.Column(
        db.Integer,
        db.ForeignKey("reserva.id_reserva", onupdate="CASCADE", ondelete="SET NULL"),
    )
    id_administrador = db.Column(
        db.Integer,
        db.ForeignKey("administrador.id_administrador", onupdate="CASCADE", ondelete="SET NULL"),
    )
    tipo = db.Column(db.String(40), nullable=False)
    canal = db.Column(db.String(20), nullable=False, default="email")
    destinatario = db.Column(db.String(150), nullable=False)
    asunto = db.Column(db.String(200), nullable=False)
    cuerpo = db.Column(db.Text, nullable=False)
    estado = db.Column(db.String(20), nullable=False, default="pendiente")
    intentos = db.Column(db.Integer, nullable=False, default=0)
    max_intentos = db.Column(db.Integer, nullable=False, default=MAX_INTENTOS_POR_DEFECTO)
    fecha_programada = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    fecha_envio = db.Column(db.DateTime)
    ultimo_error = db.Column(db.Text)
    # Clave unica: es la que hace idempotentes los recordatorios.
    clave_idempotencia = db.Column(db.String(120), unique=True)
    fecha_creacion = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    plantilla = db.relationship("PlantillaNotificacion")
    intentos_registrados = db.relationship(
        "NotificacionIntento",
        back_populates="notificacion",
        cascade="all, delete-orphan",
        order_by="NotificacionIntento.numero_intento",
    )

    @property
    def agotó_intentos(self):
        return self.intentos >= self.max_intentos

    def to_dict(self, con_historial=False):
        datos = {
            "id_notificacion": self.id_notificacion,
            "id_plantilla": self.id_plantilla,
            "id_reserva": self.id_reserva,
            "id_administrador": self.id_administrador,
            "tipo": self.tipo,
            "canal": self.canal,
            "destinatario": self.destinatario,
            "asunto": self.asunto,
            "cuerpo": self.cuerpo,
            "estado": self.estado,
            "intentos": self.intentos,
            "max_intentos": self.max_intentos,
            "fecha_programada": self.fecha_programada.isoformat() if self.fecha_programada else None,
            "fecha_envio": self.fecha_envio.isoformat() if self.fecha_envio else None,
            "ultimo_error": self.ultimo_error,
            "clave_idempotencia": self.clave_idempotencia,
            "fecha_creacion": self.fecha_creacion.isoformat() if self.fecha_creacion else None,
        }
        if con_historial:
            datos["historial"] = [i.to_dict() for i in self.intentos_registrados]
        return datos


class NotificacionIntento(db.Model):
    __tablename__ = "notificacion_intento"

    id_intento = db.Column(db.Integer, primary_key=True)
    id_notificacion = db.Column(
        db.Integer,
        db.ForeignKey("notificacion.id_notificacion", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    numero_intento = db.Column(db.Integer, nullable=False)
    canal = db.Column(db.String(20), nullable=False)
    estado = db.Column(db.String(20), nullable=False)
    detalle = db.Column(db.Text)
    fecha = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    notificacion = db.relationship("Notificacion", back_populates="intentos_registrados")

    def to_dict(self):
        return {
            "id_intento": self.id_intento,
            "id_notificacion": self.id_notificacion,
            "numero_intento": self.numero_intento,
            "canal": self.canal,
            "estado": self.estado,
            "detalle": self.detalle,
            "fecha": self.fecha.isoformat() if self.fecha else None,
        }
