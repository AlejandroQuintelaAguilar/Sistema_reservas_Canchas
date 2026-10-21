from datetime import datetime

from extensions import db

CANALES = ("email", "sms", "push")
TIPOS_PLANTILLA = (
    "reserva_confirmada",
    "reserva_modificada",
    "reserva_cancelada",
    "recordatorio_reserva",
    "nueva_reserva",
    "nueva_cancelacion",
    "nueva_modificacion",
)


class PlantillaNotificacion(db.Model):
    __tablename__ = "plantilla_notificacion"

    id_plantilla = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(40), nullable=False, unique=True)
    nombre = db.Column(db.String(100), nullable=False)
    tipo_evento = db.Column(db.String(40), nullable=False)
    canal = db.Column(db.String(20), nullable=False, default="email")
    asunto = db.Column(db.String(200), nullable=False)
    cuerpo = db.Column(db.Text, nullable=False)
    activa = db.Column(db.Boolean, nullable=False, default=True)
    id_administrador = db.Column(
        db.Integer,
        db.ForeignKey("administrador.id_administrador", onupdate="CASCADE", ondelete="SET NULL"),
    )
    fecha_creacion = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    def to_dict(self):
        return {
            "id_plantilla": self.id_plantilla,
            "codigo": self.codigo,
            "nombre": self.nombre,
            "tipo_evento": self.tipo_evento,
            "canal": self.canal,
            "asunto": self.asunto,
            "cuerpo": self.cuerpo,
            "activa": self.activa,
            "id_administrador": self.id_administrador,
            "fecha_creacion": self.fecha_creacion.isoformat() if self.fecha_creacion else None,
        }
