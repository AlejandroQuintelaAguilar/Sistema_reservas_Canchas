from extensions import db


class AnalisisGenerado(db.Model):
    """Un análisis ya calculado y guardado.

    Es la diferencia con Reporte: el reporte se recalcula cada vez que alguien
    lo pide, el análisis se persiste con los parámetros que lo generaron y con
    las métricas obtenidas, para poder consultarlo y exportarlo más tarde.
    """

    __tablename__ = "analisis_generado"

    id_analisis = db.Column(db.Integer, primary_key=True)
    tipo_analisis = db.Column(db.String(30), nullable=False)
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date, nullable=False)
    parametros = db.Column(db.JSON, nullable=False, default=dict)
    resultado = db.Column(db.JSON)
    metricas = db.Column(db.JSON)
    total_registros = db.Column(db.Integer, nullable=False, default=0)
    fecha_generado = db.Column(db.DateTime, nullable=False, default=db.func.now())
    id_administrador = db.Column(
        db.Integer,
        db.ForeignKey("administrador.id_administrador", ondelete="CASCADE"),
        nullable=False,
    )

    def to_dict(self, con_detalle=False):
        datos = {
            "id_analisis": self.id_analisis,
            "tipo_analisis": self.tipo_analisis,
            "fecha_inicio": self.fecha_inicio.isoformat() if self.fecha_inicio else None,
            "fecha_fin": self.fecha_fin.isoformat() if self.fecha_fin else None,
            "parametros": self.parametros or {},
            "total_registros": self.total_registros,
            "fecha_generado": (
                self.fecha_generado.isoformat() if self.fecha_generado else None
            ),
            "id_administrador": self.id_administrador,
        }
        if con_detalle:
            datos["resultado"] = self.resultado
            datos["metricas"] = self.metricas
        return datos
