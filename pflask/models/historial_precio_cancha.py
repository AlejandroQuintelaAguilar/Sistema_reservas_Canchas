from extensions import db


class HistorialPrecioCancha(db.Model):
    __tablename__ = "historial_precio_cancha"

    id_historial = db.Column(db.Integer, primary_key=True)
    id_cancha = db.Column(
        db.Integer,
        db.ForeignKey("cancha.id_cancha", ondelete="CASCADE"),
        nullable=False,
    )
    precio_anterior = db.Column(db.Numeric(10, 2), nullable=False)
    precio_nuevo = db.Column(db.Numeric(10, 2), nullable=False)
    id_usuario = db.Column(
        db.Integer,
        db.ForeignKey("usuario.id_usuario", ondelete="SET NULL"),
    )
    fecha = db.Column(db.DateTime, nullable=False)

    def to_dict(self):
        return {
            "id_historial": self.id_historial,
            "id_cancha": self.id_cancha,
            "precio_anterior": float(self.precio_anterior),
            "precio_nuevo": float(self.precio_nuevo),
            "id_usuario": self.id_usuario,
            "fecha": self.fecha.isoformat() if self.fecha else None,
        }