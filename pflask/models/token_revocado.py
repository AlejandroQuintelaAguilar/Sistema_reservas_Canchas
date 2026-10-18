from extensions import db


class TokenRevocado(db.Model):
    __tablename__ = "token_revocado"

    jti = db.Column(db.String(64), primary_key=True)
    id_usuario = db.Column(
        db.Integer,
        db.ForeignKey("usuario.id_usuario", ondelete="CASCADE"),
        nullable=False,
    )
    expiracion = db.Column(db.DateTime, nullable=False)
    fecha_revocacion = db.Column(db.DateTime, nullable=False)