from extensions import db


class HistorialReserva(db.Model):
    __tablename__ = "historial_reserva"

    id_historial = db.Column(db.Integer, primary_key=True)
    id_reserva = db.Column(
        db.Integer,
        db.ForeignKey("reserva.id_reserva", ondelete="CASCADE"),
        nullable=False,
    )
    tipo_cambio = db.Column(db.String(30), nullable=False)
    detalle = db.Column(db.Text)
    id_usuario = db.Column(
        db.Integer,
        db.ForeignKey("usuario.id_usuario", ondelete="SET NULL"),
    )
    fecha = db.Column(db.DateTime, nullable=False)

    def to_dict(self):
        return {
            "id_historial": self.id_historial,
            "id_reserva": self.id_reserva,
            "tipo_cambio": self.tipo_cambio,
            "detalle": self.detalle,
            "id_usuario": self.id_usuario,
            "fecha": self.fecha.isoformat() if self.fecha else None,
        }