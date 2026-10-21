from extensions import db


class TarifaCancha(db.Model):
    __tablename__ = "tarifa_cancha"

    id_tarifa = db.Column(db.Integer, primary_key=True)
    id_cancha = db.Column(
        db.Integer,
        db.ForeignKey("cancha.id_cancha", ondelete="CASCADE"),
        nullable=False,
    )
    tipo_tarifa = db.Column(db.String(20), nullable=False)
    dia_semana = db.Column(db.SmallInteger)
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fin = db.Column(db.Time, nullable=False)
    precio_hora = db.Column(db.Numeric(10, 2), nullable=False)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    id_usuario = db.Column(
        db.Integer,
        db.ForeignKey("usuario.id_usuario", ondelete="SET NULL"),
    )
    fecha = db.Column(db.DateTime, nullable=False, default=db.func.now())

    def to_dict(self):
        return {
            "id_tarifa": self.id_tarifa,
            "id_cancha": self.id_cancha,
            "tipo_tarifa": self.tipo_tarifa,
            "dia_semana": self.dia_semana,
            "dia_nombre": DIAS[self.dia_semana] if self.dia_semana is not None else "Todos",
            "hora_inicio": self.hora_inicio.strftime("%H:%M") if self.hora_inicio else None,
            "hora_fin": self.hora_fin.strftime("%H:%M") if self.hora_fin else None,
            "precio_hora": float(self.precio_hora) if self.precio_hora is not None else None,
            "activo": self.activo,
            "fecha": self.fecha.isoformat() if self.fecha else None,
        }


class HistorialTarifaCancha(db.Model):
    __tablename__ = "historial_tarifa_cancha"

    id_historial = db.Column(db.Integer, primary_key=True)
    id_tarifa = db.Column(db.Integer)
    id_cancha = db.Column(
        db.Integer,
        db.ForeignKey("cancha.id_cancha", ondelete="CASCADE"),
        nullable=False,
    )
    tipo_anterior = db.Column(db.String(20))
    tipo_nuevo = db.Column(db.String(20))
    dia_anterior = db.Column(db.SmallInteger)
    dia_nuevo = db.Column(db.SmallInteger)
    precio_anterior = db.Column(db.Numeric(10, 2))
    precio_nuevo = db.Column(db.Numeric(10, 2))
    motivo = db.Column(db.Text)
    id_usuario = db.Column(
        db.Integer,
        db.ForeignKey("usuario.id_usuario", ondelete="SET NULL"),
    )
    fecha = db.Column(db.DateTime, nullable=False, default=db.func.now())


DIAS = {
    0: "Lunes",
    1: "Martes",
    2: "Miércoles",
    3: "Jueves",
    4: "Viernes",
    5: "Sábado",
    6: "Domingo",
}

FIN_DE_SEMANA = (5, 6)
