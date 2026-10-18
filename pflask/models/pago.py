from extensions import db


# Estados del documento: Pendiente -> Pendiente de Validacion
#                       -> Aprobado / Rechazado / Expirado -> Devuelto
ESTADO_PENDIENTE = "pendiente"
ESTADO_PENDIENTE_VALIDACION = "pendiente_validacion"
ESTADO_APROBADO = "aprobado"
ESTADO_RECHAZADO = "rechazado"
ESTADO_EXPIRADO = "expirado"
ESTADO_DEVUELTO = "devuelto"

ESTADOS_PAGO = (
    ESTADO_PENDIENTE,
    ESTADO_PENDIENTE_VALIDACION,
    ESTADO_APROBADO,
    ESTADO_RECHAZADO,
    ESTADO_EXPIRADO,
    ESTADO_DEVUELTO,
)

#: Estados en los que el monto ya está dentro de la reserva (cuenta como pagado).
ESTADOS_APROBADOS = (ESTADO_APROBADO, ESTADO_DEVUELTO)
#: Estados que ya no se pueden volver a tocar.
ESTADOS_TERMINALES_PAGO = (ESTADO_RECHAZADO, ESTADO_EXPIRADO, ESTADO_DEVUELTO)

#: El documento solo define efectivo, QR y transferencia.
METODOS_DIGITALES = ("qr", "transferencia", "tarjeta")
METODOS_PAGO_VALIDOS = ("efectivo",) + METODOS_DIGITALES

ETIQUETA_ESTADO = {
    ESTADO_PENDIENTE: "Pendiente",
    ESTADO_PENDIENTE_VALIDACION: "Pendiente de validación",
    ESTADO_APROBADO: "Aprobado",
    ESTADO_RECHAZADO: "Rechazado",
    ESTADO_EXPIRADO: "Expirado",
    ESTADO_DEVUELTO: "Devuelto",
}


class Pago(db.Model):
    __tablename__ = "pago"

    id_pago = db.Column(db.Integer, primary_key=True)
    metodo_pago = db.Column(db.String(50), nullable=False)
    estado_pago = db.Column(db.String(30), nullable=False, default=ESTADO_PENDIENTE)
    monto = db.Column(db.Numeric(10, 2), nullable=False)
    fecha_pago = db.Column(db.DateTime, nullable=False, default=db.func.now())

    #: Clave de idempotencia: dos peticiones con la misma referencia son el mismo pago.
    referencia = db.Column(db.String(60), unique=True)
    #: Ruta del comprobante subido (NULL si el pago fue efectivo en caja).
    comprobante = db.Column(db.String(255))
    nombre_original = db.Column(db.String(255))
    content_type = db.Column(db.String(100))
    tamano_bytes = db.Column(db.Integer)
    sha256 = db.Column(db.String(64))

    fecha_validacion = db.Column(db.DateTime)
    id_usuario_validador = db.Column(db.Integer)
    motivo_rechazo = db.Column(db.Text)

    monto_devuelto = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    fecha_devolucion = db.Column(db.DateTime)
    motivo_devolucion = db.Column(db.Text)

    id_reserva = db.Column(
        db.Integer,
        db.ForeignKey("reserva.id_reserva"),
        nullable=False,
    )
    id_empleado = db.Column(
        db.Integer,
        db.ForeignKey("empleado.id_empleado"),
        nullable=True,
    )
    id_usuario = db.Column(
        db.Integer,
        db.ForeignKey("usuario.id_usuario", ondelete="SET NULL"),
        nullable=True,
    )

    reserva = db.relationship("Reserva")
    empleado = db.relationship("Empleado")

    @property
    def es_aprobado(self):
        return self.estado_pago in ESTADOS_APROBADOS

    @property
    def saldo_restante(self):
        """Cuánto falta por devolver de este pago (0 si no fue devuelto)."""
        return round(float(self.monto) - float(self.monto_devuelto or 0), 2)

    def to_dict(self):
        return {
            "id_pago": self.id_pago,
            "metodo_pago": self.metodo_pago,
            "estado_pago": self.estado_pago,
            "estado_label": ETIQUETA_ESTADO.get(self.estado_pago, self.estado_pago),
            "monto": float(self.monto) if self.monto is not None else None,
            "monto_devuelto": float(self.monto_devuelto or 0),
            "saldo_restante": self.saldo_restante,
            "fecha_pago": self.fecha_pago.isoformat() if self.fecha_pago else None,
            "fecha_validacion": (
                self.fecha_validacion.isoformat() if self.fecha_validacion else None
            ),
            "fecha_devolucion": (
                self.fecha_devolucion.isoformat() if self.fecha_devolucion else None
            ),
            "referencia": self.referencia,
            "comprobante": self.comprobante,
            "sha256": self.sha256,
            "nombre_original": self.nombre_original,
            "content_type": self.content_type,
            "tamano_bytes": self.tamano_bytes,
            "motivo_rechazo": self.motivo_rechazo,
            "motivo_devolucion": self.motivo_devolucion,
            "id_reserva": self.id_reserva,
            "id_empleado": self.id_empleado,
            "id_usuario": self.id_usuario,
            "id_usuario_validador": self.id_usuario_validador,
        }


class PagoAuditoria(db.Model):
    """Revision del comprobante contra el pago (solo administrador)."""

    __tablename__ = "pago_auditoria"

    id_auditoria = db.Column(db.Integer, primary_key=True)
    id_pago = db.Column(
        db.Integer,
        db.ForeignKey("pago.id_pago", ondelete="CASCADE"),
        nullable=False,
    )
    id_usuario = db.Column(
        db.Integer,
        db.ForeignKey("usuario.id_usuario", ondelete="SET NULL"),
        nullable=True,
    )
    resultado = db.Column(db.String(20), nullable=False, default="conforme")
    monto_comprobante = db.Column(db.Numeric(10, 2))
    fecha_comprobante = db.Column(db.Date)
    metodo_comprobante = db.Column(db.String(50))
    referencia_comprobante = db.Column(db.String(100))
    observaciones = db.Column(db.Text)
    fecha = db.Column(db.DateTime, nullable=False, default=db.func.now())

    def to_dict(self):
        return {
            "id_auditoria": self.id_auditoria,
            "id_pago": self.id_pago,
            "resultado": self.resultado,
            "monto_comprobante": (
                float(self.monto_comprobante) if self.monto_comprobante is not None else None
            ),
            "fecha_comprobante": (
                self.fecha_comprobante.isoformat() if self.fecha_comprobante else None
            ),
            "metodo_comprobante": self.metodo_comprobante,
            "referencia_comprobante": self.referencia_comprobante,
            "observaciones": self.observaciones,
            "fecha": self.fecha.isoformat() if self.fecha else None,
            "id_usuario": self.id_usuario,
        }


class DevolucionSolicitud(db.Model):
    """El cliente solicita la devolucion; el empleado la aprueba o rechaza."""

    __tablename__ = "devolucion_solicitud"

    id_solicitud = db.Column(db.Integer, primary_key=True)
    id_pago = db.Column(
        db.Integer,
        db.ForeignKey("pago.id_pago", ondelete="CASCADE"),
        nullable=False,
    )
    id_cliente = db.Column(
        db.Integer,
        db.ForeignKey("cliente.id_cliente", ondelete="SET NULL"),
        nullable=True,
    )
    id_usuario_solicitante = db.Column(
        db.Integer,
        db.ForeignKey("usuario.id_usuario", ondelete="SET NULL"),
        nullable=True,
    )
    id_usuario_decision = db.Column(
        db.Integer,
        db.ForeignKey("usuario.id_usuario", ondelete="SET NULL"),
        nullable=True,
    )
    monto = db.Column(db.Numeric(10, 2), nullable=False)
    motivo = db.Column(db.Text, nullable=False)
    estado = db.Column(db.String(20), nullable=False, default="solicitada")
    motivo_decision = db.Column(db.Text)
    monto_devuelto = db.Column(db.Numeric(10, 2))
    fecha_devolucion = db.Column(db.DateTime)
    fecha_solicitud = db.Column(db.DateTime, nullable=False, default=db.func.now())
    fecha_decision = db.Column(db.DateTime)

    pago = db.relationship("Pago")

    def to_dict(self):
        return {
            "id_solicitud": self.id_solicitud,
            "id_pago": self.id_pago,
            "id_cliente": self.id_cliente,
            "monto": float(self.monto) if self.monto is not None else None,
            "motivo": self.motivo,
            "estado": self.estado,
            "motivo_decision": self.motivo_decision,
            "monto_devuelto": (
                float(self.monto_devuelto) if self.monto_devuelto is not None else None
            ),
            "fecha_devolucion": (
                self.fecha_devolucion.isoformat() if self.fecha_devolucion else None
            ),
            "fecha_solicitud": self.fecha_solicitud.isoformat() if self.fecha_solicitud else None,
            "fecha_decision": (
                self.fecha_decision.isoformat() if self.fecha_decision else None
            ),
            "id_usuario_solicitante": self.id_usuario_solicitante,
            "id_usuario_decision": self.id_usuario_decision,
        }


class TurnoCaja(db.Model):
    """Arqueo del efectivo del turno. Al cerrar, la caja no admite movimientos."""

    __tablename__ = "turno_caja"

    id_turno = db.Column(db.Integer, primary_key=True)
    id_empleado = db.Column(
        db.Integer,
        db.ForeignKey("empleado.id_empleado", ondelete="RESTRICT"),
        nullable=False,
    )
    id_usuario_cierre = db.Column(
        db.Integer,
        db.ForeignKey("usuario.id_usuario", ondelete="SET NULL"),
        nullable=True,
    )
    fecha = db.Column(db.Date, nullable=False, default=db.func.current_date())
    hora_apertura = db.Column(db.DateTime, nullable=False, default=db.func.now())
    hora_cierre = db.Column(db.DateTime)

    monto_esperado_efectivo = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    monto_fisico = db.Column(db.Numeric(12, 2))
    diferencia = db.Column(db.Numeric(12, 2))
    total_qr = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_transferencia = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_tarjeta = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    cantidad_pagos = db.Column(db.Integer, nullable=False, default=0)
    cantidad_devoluciones = db.Column(db.Integer, nullable=False, default=0)
    estado = db.Column(db.String(20), nullable=False, default="abierto")
    observaciones = db.Column(db.Text)

    empleado = db.relationship("Empleado")

    @property
    def nombre_empleado(self):
        """El nombre del empleado vive en Persona, via Usuario."""
        from models.empleado import Empleado
        from models.usuario import Usuario
        from models.persona import Persona

        emp = self.empleado or db.session.get(Empleado, self.id_empleado)
        if not emp or not emp.id_usuario:
            return None
        usuario = db.session.get(Usuario, emp.id_usuario)
        if not usuario or not usuario.id_persona:
            return None
        persona = db.session.get(Persona, usuario.id_persona)
        if not persona:
            return None
        return f"{persona.nombre} {persona.apellido}".strip()

    @property
    def total_digital(self):
        return round(
            float(self.total_qr or 0)
            + float(self.total_transferencia or 0)
            + float(self.total_tarjeta or 0),
            2,
        )

    def to_dict(self):
        return {
            "id_turno": self.id_turno,
            "id_empleado": self.id_empleado,
            "empleado": self.nombre_empleado,
            "fecha": self.fecha.isoformat() if self.fecha else None,
            "hora_apertura": self.hora_apertura.isoformat() if self.hora_apertura else None,
            "hora_cierre": self.hora_cierre.isoformat() if self.hora_cierre else None,
            "monto_esperado_efectivo": float(self.monto_esperado_efectivo or 0),
            "monto_fisico": float(self.monto_fisico) if self.monto_fisico is not None else None,
            "diferencia": float(self.diferencia) if self.diferencia is not None else None,
            "total_qr": float(self.total_qr or 0),
            "total_transferencia": float(self.total_transferencia or 0),
            "total_tarjeta": float(self.total_tarjeta or 0),
            "total_digital": self.total_digital,
            "cantidad_pagos": self.cantidad_pagos,
            "cantidad_devoluciones": self.cantidad_devoluciones,
            "estado": self.estado,
            "observaciones": self.observaciones,
            "id_usuario_cierre": self.id_usuario_cierre,
        }
