from extensions import db
from models.tarifa_cancha import DIAS


class HorarioCancha(db.Model):
    __tablename__ = "horario_cancha"

    id_horario = db.Column(db.Integer, primary_key=True)
    id_cancha = db.Column(
        db.Integer,
        db.ForeignKey("cancha.id_cancha", ondelete="CASCADE"),
        nullable=False,
    )
    dia_semana = db.Column(db.SmallInteger, nullable=False)
    hora_apertura = db.Column(db.Time, nullable=False)
    hora_cierre = db.Column(db.Time, nullable=False)
    activo = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self):
        return {
            "id_horario": self.id_horario,
            "id_cancha": self.id_cancha,
            "dia_semana": self.dia_semana,
            "dia_nombre": DIAS.get(self.dia_semana),
            "hora_apertura": (
                self.hora_apertura.strftime("%H:%M") if self.hora_apertura else None
            ),
            "hora_cierre": self.hora_cierre.strftime("%H:%M") if self.hora_cierre else None,
            "activo": self.activo,
            "por_defecto": False,
        }
