-- =====================================================================
-- ANALITICA DE DATOS - Persistencia de resultados y correccion de estados
-- Proyecto: Pagina web de canchas (seccion 7 de logica_de_negocio_canchas)
--
-- Ejecutar DESPUES de db_analitica_canchas.sql y db_analitica_empleados.sql.
-- Es idempotente: se puede volver a aplicar sin romper nada.
--
-- Este script hace dos cosas:
--   1. Crea la tabla ANALISIS_GENERADO, que es la diferencia clave entre un
--      reporte (se calcula al vuelo) y un analisis (se guarda y se consulta
--      despues).
--   2. Corrige las vistas y funciones analiticas:Todas usaban estados que ya
--      no existen en el proyecto.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. TABLA DE PERSISTENCIA: ANALISIS_GENERADO
-- ---------------------------------------------------------------------
-- Guarda los PARAMETROS con los que se pidio el analisis y el RESULTADO con
-- las metricas calculadas, para poder consultarlo mas tarde.
CREATE TABLE IF NOT EXISTS analisis_generado (
    id_analisis       SERIAL PRIMARY KEY,
    tipo_analisis     VARCHAR(30) NOT NULL,
    fecha_inicio      DATE NOT NULL,
    fecha_fin         DATE NOT NULL,
    parametros        JSONB NOT NULL DEFAULT '{}'::jsonb,
    resultado         JSONB,
    metricas          JSONB,
    total_registros   INTEGER NOT NULL DEFAULT 0,
    fecha_generado    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    id_administrador  INTEGER NOT NULL
        REFERENCES administrador(id_administrador) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT chk_analisis_tipo
        CHECK (tipo_analisis IN ('reservas', 'pagos', 'canchas', 'clientes')),
    -- El documento pide validar que la fecha final sea posterior o igual a la
    -- inicial. Se refuerza en la base, no solo en el codigo.
    CONSTRAINT chk_analisis_rango CHECK (fecha_fin >= fecha_inicio)
);

-- Indices para los filtros del listado: por tipo y por fecha de generacion.
CREATE INDEX IF NOT EXISTS idx_analisis_tipo   ON analisis_generado (tipo_analisis);
CREATE INDEX IF NOT EXISTS idx_analisis_fecha  ON analisis_generado (fecha_generado DESC);


-- ---------------------------------------------------------------------
-- 2. CORRECCION DE ESTADOS EN LAS VISTAS Y FUNCIONES
-- ---------------------------------------------------------------------
-- El proyecto quedo con seis estados de pago:
--   pendiente, pendiente_validacion, aprobado, rechazado, expirado, devuelto
-- Las vistas y funciones filtraban por 'pagado' y 'reembolsado', que ya no
-- existen, asi que devolvian siempre cero o sumaban de menos.
-- Los estados de reserva SI son estos (la etiqueta de negocio los renombra):
--   pendiente(Reservada), confirmada, completada(Finalizada),
--   cancelada, expirada
-- =====================================================================


-- 2.1 Pagos aprobados por fecha y metodo.
CREATE OR REPLACE VIEW vista_analitica_pagos AS
SELECT p.fecha_pago::DATE        AS fecha,
       p.metodo_pago,
       COUNT(*)                  AS cantidad_pagos,
       COALESCE(SUM(p.monto), 0) AS monto_total
FROM pago p
WHERE p.estado_pago = 'aprobado'
GROUP BY p.fecha_pago::DATE, p.metodo_pago;


-- 2.2 Reservas por fecha, cancha, deporte y estado.
CREATE OR REPLACE VIEW vista_analitica_reservas AS
SELECT r.fecha_reserva,
       c.id_cancha,
       c.nombre_cancha,
       c.tipo_deporte,
       r.estado_reserva,
       COUNT(*) AS cantidad
FROM reserva r
JOIN cancha c ON c.id_cancha = r.id_cancha
GROUP BY r.fecha_reserva, c.id_cancha, c.nombre_cancha, c.tipo_deporte,
         r.estado_reserva;


-- 2.3 Clientes: reservas, gasto y ventana de actividad.
CREATE OR REPLACE VIEW vista_analitica_clientes AS
SELECT cl.id_cliente,
       per.nombre || ' ' || per.apellido AS nombre_completo,
       COUNT(r.id_reserva) AS total_reservas,
       COALESCE(SUM(r.monto_total) FILTER (
           WHERE r.estado_reserva IN ('confirmada', 'completada')), 0) AS total_gastado,
       MIN(r.fecha_reserva) AS primera_reserva,
       MAX(r.fecha_reserva) AS ultima_reserva
FROM cliente cl
JOIN usuario u  ON u.id_usuario = cl.id_usuario
JOIN persona per ON per.id_persona = u.id_persona
LEFT JOIN reserva r ON r.id_cliente = cl.id_cliente
GROUP BY cl.id_cliente, per.nombre, per.apellido;


-- 2.4 Productividad de empleados.
CREATE OR REPLACE VIEW vista_analitica_empleados AS
SELECT e.id_empleado,
       per.nombre || ' ' || per.apellido AS nombre_empleado,
       e.cargo,
       e.turno_laboral,
       e.fecha_contratacion,
       e.salario,
       COUNT(p.id_pago) FILTER (WHERE p.estado_pago = 'aprobado') AS pagos_procesados,
       COALESCE(SUM(p.monto) FILTER (WHERE p.estado_pago = 'aprobado'), 0) AS total_recaudado,
       COALESCE(SUM(p.monto) FILTER (
           WHERE p.estado_pago IN ('pendiente', 'pendiente_validacion')), 0) AS por_cobrar
FROM empleado e
JOIN usuario u    ON u.id_usuario = e.id_usuario
JOIN persona per  ON per.id_persona = u.id_persona
LEFT JOIN pago p  ON p.id_empleado = e.id_empleado
GROUP BY e.id_empleado, per.nombre, per.apellido, e.cargo, e.turno_laboral,
         e.fecha_contratacion, e.salario;


-- 2.5 Ganancias mensuales: ingresos, por cobrar y reembolsos.
-- El documento define INGRESOS = pagos aprobados - devoluciones, asi que el
-- neto se calcula aparte en vez de mezclarlo con el bruto.
CREATE OR REPLACE VIEW vista_ganancias_mensuales AS
SELECT date_trunc('month', fecha_pago)::date AS mes,
       COUNT(*) FILTER (WHERE estado_pago = 'aprobado') AS cantidad_pagados,
       COALESCE(SUM(monto) FILTER (WHERE estado_pago = 'aprobado'), 0) AS ingresos,
       COALESCE(SUM(monto) FILTER (
           WHERE estado_pago IN ('pendiente', 'pendiente_validacion')), 0) AS por_cobrar,
       COALESCE(SUM(monto_devuelto) FILTER (
           WHERE estado_pago = 'devuelto'), 0) AS reembolsos
FROM pago
GROUP BY 1;


-- 2.6 Saldo por cliente. El pagado descuenta lo devuelto.
CREATE OR REPLACE VIEW vista_saldos_clientes AS
SELECT cl.id_cliente,
       per.nombre || ' ' || per.apellido AS nombre_cliente,
       cl.fecha_afiliacion,
       COALESCE(SUM(r.monto_total), 0) AS total_comprometido,
       COALESCE((
           SELECT COALESCE(SUM(p.monto), 0) - COALESCE(SUM(p.monto_devuelto), 0)
             FROM pago p
             JOIN reserva r2 ON r2.id_reserva = p.id_reserva
            WHERE r2.id_cliente = cl.id_cliente
              AND p.estado_pago IN ('aprobado', 'devuelto')
       ), 0) AS total_pagado,
       COALESCE(SUM(r.monto_total), 0) - COALESCE((
           SELECT COALESCE(SUM(p.monto), 0) - COALESCE(SUM(p.monto_devuelto), 0)
             FROM pago p
             JOIN reserva r2 ON r2.id_reserva = p.id_reserva
            WHERE r2.id_cliente = cl.id_cliente
              AND p.estado_pago IN ('aprobado', 'devuelto')
       ), 0) AS saldo_pendiente
FROM cliente cl
JOIN usuario u    ON u.id_usuario = cl.id_usuario
JOIN persona per  ON per.id_persona = u.id_persona
LEFT JOIN reserva r ON r.id_cliente = cl.id_cliente
GROUP BY cl.id_cliente, per.nombre, per.apellido, cl.fecha_afiliacion;


-- ---------------------------------------------------------------------
-- 3. FUNCIONES CORREGIDAS
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_saldo_pendiente(p_id_reserva INTEGER) RETURNS NUMERIC AS $$
DECLARE
    v_monto_total NUMERIC;
    v_pagado      NUMERIC;
BEGIN
    SELECT monto_total INTO v_monto_total FROM reserva WHERE id_reserva = p_id_reserva;

    -- Solo lo aprobado cuenta, y lo devuelto se resta.
    SELECT COALESCE(SUM(monto), 0) - COALESCE(SUM(monto_devuelto), 0)
      INTO v_pagado
      FROM pago
     WHERE id_reserva = p_id_reserva
       AND estado_pago IN ('aprobado', 'devuelto');

    RETURN v_monto_total - v_pagado;
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION fn_resumen_diario(p_fecha DATE)
RETURNS TABLE (
    total_reservas      BIGINT,
    horas_reservadas    INTERVAL,
    ingresos_pagados    NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT COUNT(*)::BIGINT,
           COALESCE(SUM(r.hora_fin - r.hora_inicio), INTERVAL '0'),
           COALESCE((
               SELECT COALESCE(SUM(p.monto), 0) - COALESCE(SUM(p.monto_devuelto), 0)
                 FROM pago p
                WHERE p.fecha_pago::DATE = p_fecha
                  AND p.estado_pago IN ('aprobado', 'devuelto')
           ), 0)
    FROM reserva r
    WHERE r.fecha_reserva = p_fecha;
END;
$$ LANGUAGE plpgsql;


-- Las horas que cuentan para OCUPACION son las de reservas confirmadas o
-- finalizadas. Antes tomaba cualquier estado distinto de 'cancelada', asi que
-- una reserva pendiente o expirada inflaba la ocupacion.
CREATE OR REPLACE FUNCTION fn_horas_cancha(
    p_id_cancha INTEGER, p_desde DATE, p_hasta DATE
)
RETURNS TABLE (
    fecha_dia          DATE,
    horas_reservadas   NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT r.fecha_reserva,
           COALESCE(SUM(
               EXTRACT(EPOCH FROM (r.hora_fin - r.hora_inicio)) / 3600.0
           ), 0)
    FROM reserva r
    WHERE r.id_cancha = p_id_cancha
      AND r.fecha_reserva BETWEEN p_desde AND p_hasta
      AND r.estado_reserva IN ('confirmada', 'completada')
    GROUP BY r.fecha_reserva
    ORDER BY r.fecha_reserva;
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION fn_estado_financiero_reserva(p_id_reserva INTEGER)
RETURNS TABLE (
    monto_total      NUMERIC,
    monto_pagado     NUMERIC,
    saldo_pendiente  NUMERIC,
    estado_reserva   VARCHAR(20)
) AS $$
BEGIN
    RETURN QUERY
    SELECT r.monto_total,
           COALESCE((
               SELECT COALESCE(SUM(p.monto), 0) - COALESCE(SUM(p.monto_devuelto), 0)
                 FROM pago p
                WHERE p.id_reserva = r.id_reserva
                  AND p.estado_pago IN ('aprobado', 'devuelto')
           ), 0),
           r.monto_total - COALESCE((
               SELECT COALESCE(SUM(p.monto), 0) - COALESCE(SUM(p.monto_devuelto), 0)
                 FROM pago p
                WHERE p.id_reserva = r.id_reserva
                  AND p.estado_pago IN ('aprobado', 'devuelto')
           ), 0),
           r.estado_reserva
    FROM reserva r
    WHERE r.id_reserva = p_id_reserva;
END;
$$ LANGUAGE plpgsql;
