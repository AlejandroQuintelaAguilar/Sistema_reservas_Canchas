from extensions import db


class HistorialEstadoCancha(db.Model):
    __tablename__ = "historial_estado_cancha"

    id_historial = db.Column(db.Integer, primary_key=True)
    id_cancha = db.Column(
        db.Integer,
        db.ForeignKey("cancha.id_cancha", ondelete="CASCADE"),
        nullable=False,
    )
    estado_anterior = db.Column(db.String(20), nullable=False)
    estado_nuevo = db.Column(db.String(20), nullable=False)
    motivo = db.Column(db.String(300))
    id_usuario = db.Column(
        db.Integer,
        db.ForeignKey("usuario.id_usuario", ondelete="SET NULL"),
    )
    fecha = db.Column(db.DateTime, nullable=False)

    def to_dict(self):
        return {
            "id_historial": self.id_historial,
            "id_cancha": self.id_cancha,
            "estado_anterior": self.estado_anterior,
            "estado_nuevo": self.estado_nuevo,
            "motivo": self.motivo,
            "id_usuario": self.id_usuario,
            "fecha": self.fecha.isoformat() if self.fecha else None,
        }