-- =====================================================================
-- MODULO DE NOTIFICACIONES (plantillas, envios e historial de intentos)
-- Ejecutar sobre la base proyectoCanchas. Es idempotente: se puede correr
-- mas de una vez sin romper nada.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. PLANTILLAS
--    El flujo del documento es: elegir plantilla -> guardar la
--    notificacion como PENDIENTE -> enviar por el canal -> ENVIADO.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS plantilla_notificacion (
    id_plantilla        SERIAL PRIMARY KEY,
    codigo              VARCHAR(40)  NOT NULL UNIQUE,
    nombre              VARCHAR(100) NOT NULL,
    tipo_evento         VARCHAR(40)  NOT NULL,
    canal               VARCHAR(20)  NOT NULL DEFAULT 'email',
    asunto              VARCHAR(200) NOT NULL,
    cuerpo              TEXT         NOT NULL,
    activa              BOOLEAN      NOT NULL DEFAULT TRUE,
    id_administrador    INTEGER      REFERENCES administrador(id_administrador) ON UPDATE CASCADE ON DELETE SET NULL,
    fecha_creacion      TIMESTAMP    NOT NULL DEFAULT NOW(),
    CONSTRAINT plantilla_canal_valido
        CHECK (canal IN ('email', 'sms', 'push')),
    CONSTRAINT plantilla_tipo_valido
        CHECK (tipo_evento IN ('reserva_confirmada', 'reserva_modificada',
                               'reserva_cancelada', 'recordatorio_reserva',
                               'nueva_reserva', 'nueva_cancelacion',
                               'nueva_modificacion'))
);
COMMENT ON TABLE plantilla_notificacion IS
    'Plantillas reutilizables con marcadores {nombre_cliente}, {fecha_reserva}, etc.';

-- ---------------------------------------------------------------------
-- 2. NOTIFICACIONES
--    Una fila por aviso. clave_idempotencia es lo que impide que el
--    recordatorio programado mande el mismo mensaje dos veces.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notificacion (
    id_notificacion        SERIAL PRIMARY KEY,
    id_plantilla           INTEGER      REFERENCES plantilla_notificacion(id_plantilla) ON UPDATE CASCADE ON DELETE SET NULL,
    id_reserva             INTEGER      REFERENCES reserva(id_reserva)           ON UPDATE CASCADE ON DELETE SET NULL,
    id_administrador       INTEGER      REFERENCES administrador(id_administrador) ON UPDATE CASCADE ON DELETE SET NULL,
    tipo                   VARCHAR(40)  NOT NULL,
    canal                  VARCHAR(20)  NOT NULL DEFAULT 'email',
    destinatario           VARCHAR(150) NOT NULL,
    asunto                 VARCHAR(200) NOT NULL,
    cuerpo                 TEXT         NOT NULL,
    estado                 VARCHAR(20)  NOT NULL DEFAULT 'pendiente',
    intentos               INTEGER      NOT NULL DEFAULT 0,
    max_intentos           INTEGER      NOT NULL DEFAULT 3,
    fecha_programada       TIMESTAMP    NOT NULL DEFAULT NOW(),
    fecha_envio            TIMESTAMP,
    ultimo_error           TEXT,
    clave_idempotencia     VARCHAR(120) UNIQUE,
    fecha_creacion         TIMESTAMP    NOT NULL DEFAULT NOW(),
    CONSTRAINT notificacion_estado_valido
        CHECK (estado IN ('pendiente', 'enviado', 'fallido')),
    CONSTRAINT notificacion_canal_valido
        CHECK (canal IN ('email', 'sms', 'push')),
    CONSTRAINT notificacion_intentos_no_negativos
        CHECK (intentos >= 0 AND max_intentos > 0)
);
COMMENT ON TABLE notificacion IS
    'Avisos enviados a clientes y administradores. PENDIENTE -> ENVIADO o FALLIDO.';

-- El worker toma lo pendiente por orden de programación.
CREATE INDEX IF NOT EXISTS ix_notificacion_pendientes
    ON notificacion (estado, fecha_programada);

-- ---------------------------------------------------------------------
-- 3. HISTORIAL DE INTENTOS
--    "Si falla -> FALLIDO, se registra el error y se reintenta con limite
--    de intentos." Cada intento queda con su error.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notificacion_intento (
    id_intento         SERIAL PRIMARY KEY,
    id_notificacion    INTEGER      NOT NULL REFERENCES notificacion(id_notificacion) ON UPDATE CASCADE ON DELETE CASCADE,
    numero_intento     INTEGER      NOT NULL,
    canal              VARCHAR(20)  NOT NULL,
    estado             VARCHAR(20)  NOT NULL,
    detalle            TEXT,
    fecha              TIMESTAMP    NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_intento_notificacion
    ON notificacion_intento (id_notificacion, numero_intento);

-- ---------------------------------------------------------------------
-- 4. PLANTILLAS DEL SISTEMA
--    Se insertan una sola vez; si ya existen no se pisan.
-- ---------------------------------------------------------------------
INSERT INTO plantilla_notificacion
    (codigo, nombre, tipo_evento, canal, asunto, cuerpo)
VALUES
    ('RESERVA_CONFIRMADA', 'Reserva confirmada', 'reserva_confirmada', 'email',
     'Reserva confirmada en {nombre_complejo}',
     'Hola {nombre_cliente}, tu reserva del {fecha_reserva} de {hora_inicio} a {hora_fin} en {nombre_cancha} quedo confirmada. Tu codigo es {codigo_reserva}.'),

    ('RESERVA_MODIFICADA', 'Reserva modificada', 'reserva_modificada', 'email',
     'Tu reserva cambio',
     'Hola {nombre_cliente}, tu reserva del {fecha_reserva} fue modificada. Ahora es de {hora_inicio} a {hora_fin} en {nombre_cancha}. Codigo {codigo_reserva}.'),

    ('RESERVA_CANCELADA', 'Reserva cancelada', 'reserva_cancelada', 'email',
     'Reserva cancelada',
     'Hola {nombre_cliente}, tu reserva del {fecha_reserva} en {nombre_cancha} fue cancelada. Codigo {codigo_reserva}.'),

    ('RECORDATORIO_RESERVA', 'Recordatorio del dia anterior', 'recordatorio_reserva', 'email',
     'Recordatorio: tu reserva es manana',
     'Hola {nombre_cliente}, te recordamos tu reserva de manana {fecha_reserva} de {hora_inicio} a {hora_fin} en {nombre_cancha}. Codigo {codigo_reserva}.'),

    ('NUEVA_RESERVA', 'Aviso al admin: nueva reserva', 'nueva_reserva', 'email',
     'Nueva reserva registrada',
     'Se registro la reserva {codigo_reserva} del cliente {nombre_cliente} para el {fecha_reserva} de {hora_inicio} a {hora_fin} en {nombre_cancha}.'),

    ('NUEVA_CANCELACION', 'Aviso al admin: cancelacion', 'nueva_cancelacion', 'email',
     'Reserva cancelada por el cliente',
     'El cliente {nombre_cliente} cancelo la reserva {codigo_reserva} del {fecha_reserva} en {nombre_cancha}.'),

    ('NUEVA_MODIFICACION', 'Aviso al admin: modificacion', 'nueva_modificacion', 'email',
     'Reserva modificada por el cliente',
     'El cliente {nombre_cliente} modifico la reserva {codigo_reserva}. Ahora es del {fecha_reserva} de {hora_inicio} a {hora_fin} en {nombre_cancha}.')
ON CONFLICT (codigo) DO NOTHING;
