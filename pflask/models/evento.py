from extensions import db

evento_cancha = db.Table(
    "evento_cancha",
    db.Column(
        "id_evento",
        db.Integer,
        db.ForeignKey("evento.id_evento", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "id_cancha",
        db.Integer,
        db.ForeignKey("cancha.id_cancha", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
    ),
)


class Evento(db.Model):
    __tablename__ = "evento"

    id_evento = db.Column(db.Integer, primary_key=True)
    nombre_evento = db.Column(db.String(100), nullable=False)
    tipo_evento = db.Column(db.String(50), nullable=True)
    fecha_evento = db.Column(db.Date, nullable=False)
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fin = db.Column(db.Time, nullable=False)
    cupo_maximo = db.Column(db.Integer, nullable=True)
    organizador = db.Column(db.String(100), nullable=True)
    contacto = db.Column(db.String(30), nullable=True)
    descripcion = db.Column(db.Text, nullable=True)
    id_cancha = db.Column(db.Integer, db.ForeignKey("cancha.id_cancha"), nullable=False)

    # Relación con la cancha principal (retrocompatibilidad con schema.sql)
    cancha = db.relationship("Cancha", foreign_keys=[id_cancha])

    # Relación muchos-a-muchos para reservar una o más canchas en un mismo evento
    canchas = db.relationship("Cancha", secondary=evento_cancha, lazy="selectin")

    def obtener_canchas_ordenadas(self):
        lista = list(self.canchas) if self.canchas else []
        if self.cancha and all(c.id_cancha != self.cancha.id_cancha for c in lista):
            lista.insert(0, self.cancha)
        return sorted(
            lista,
            key=lambda c: (0 if c.id_cancha == self.id_cancha else 1, c.id_cancha),
        )

    def to_dict(self):
        canchas_asociadas = self.obtener_canchas_ordenadas()
        ids_canchas = (
            [c.id_cancha for c in canchas_asociadas]
            if canchas_asociadas
            else ([self.id_cancha] if self.id_cancha else [])
        )
        nombres_canchas = [
            c.nombre_cancha for c in canchas_asociadas if c.nombre_cancha
        ]
        nombre_cancha_str = (
            ", ".join(nombres_canchas)
            if nombres_canchas
            else (self.cancha.nombre_cancha if self.cancha else None)
        )

        return {
            "id_evento": self.id_evento,
            "nombre_evento": self.nombre_evento,
            "tipo_evento": self.tipo_evento,
            "fecha_evento": self.fecha_evento.isoformat() if self.fecha_evento else None,
            "hora_inicio": self.hora_inicio.strftime("%H:%M") if self.hora_inicio else None,
            "hora_fin": self.hora_fin.strftime("%H:%M") if self.hora_fin else None,
            "cupo_maximo": self.cupo_maximo,
            "organizador": self.organizador,
            "contacto": self.contacto,
            "descripcion": self.descripcion,
            "id_cancha": self.id_cancha,
            "nombre_cancha": nombre_cancha_str,
            "ids_canchas": ids_canchas,
            "nombres_canchas": nombres_canchas,
            "canchas_detalle": [
                {
                    "id_cancha": c.id_cancha,
                    "nombre_cancha": c.nombre_cancha,
                    "tipo_deporte": c.tipo_deporte,
                }
                for c in canchas_asociadas
            ],
        }
