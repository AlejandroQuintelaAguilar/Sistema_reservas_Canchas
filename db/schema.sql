--
-- PostgreSQL database dump
--

\restrict FxtAANkAKCg7GBym9ipYbSc7F7o5OM4A1lviQ5ccO7iXmN9Vrpc7cFAa3Gd9jpj

-- Dumped from database version 18.6
-- Dumped by pg_dump version 18.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: administrador; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.administrador (
    id_administrador integer NOT NULL,
    nivel_acceso character varying(30) NOT NULL,
    fecha_designado date DEFAULT CURRENT_DATE NOT NULL,
    area_responsabilidad character varying(100),
    id_usuario integer NOT NULL
);


--
-- Name: administrador_id_administrador_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.administrador_id_administrador_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: administrador_id_administrador_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.administrador_id_administrador_seq OWNED BY public.administrador.id_administrador;


--
-- Name: cancha; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cancha (
    id_cancha integer NOT NULL,
    nombre_cancha character varying(80) NOT NULL,
    tipo_deporte character varying(50) NOT NULL,
    precio_hora numeric(10,2) NOT NULL,
    ubicacion character varying(150),
    estado character varying(20) DEFAULT 'disponible'::character varying NOT NULL,
    techada boolean DEFAULT false NOT NULL,
    superficie character varying(50),
    id_categoria integer NOT NULL,
    id_administrador integer NOT NULL,
    CONSTRAINT cancha_precio_hora_check CHECK ((precio_hora > (0)::numeric)),
    CONSTRAINT chk_cancha_estado CHECK (((estado)::text = ANY ((ARRAY['disponible'::character varying, 'mantenimiento'::character varying, 'fuera_servicio'::character varying])::text[])))
);


--
-- Name: cancha_id_cancha_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.cancha_id_cancha_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cancha_id_cancha_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.cancha_id_cancha_seq OWNED BY public.cancha.id_cancha;


--
-- Name: categoria; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.categoria (
    id_categoria integer NOT NULL,
    nombre character varying(50) NOT NULL,
    descripcion text
);


--
-- Name: categoria_id_categoria_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.categoria_id_categoria_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: categoria_id_categoria_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.categoria_id_categoria_seq OWNED BY public.categoria.id_categoria;


--
-- Name: cliente; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cliente (
    id_cliente integer NOT NULL,
    fecha_afiliacion date DEFAULT CURRENT_DATE NOT NULL,
    deporte_pref character varying(50),
    historial_reservas text,
    id_usuario integer NOT NULL
);


--
-- Name: cliente_id_cliente_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.cliente_id_cliente_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cliente_id_cliente_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.cliente_id_cliente_seq OWNED BY public.cliente.id_cliente;


--
-- Name: elige; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.elige (
    id_cliente integer NOT NULL,
    id_cancha integer NOT NULL
);


--
-- Name: empleado; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.empleado (
    id_empleado integer NOT NULL,
    cargo character varying(50) NOT NULL,
    turno_laboral character varying(30),
    fecha_contratacion date DEFAULT CURRENT_DATE NOT NULL,
    salario numeric(10,2) NOT NULL,
    id_administrador integer NOT NULL,
    id_usuario integer,
    CONSTRAINT empleado_salario_check CHECK ((salario >= (0)::numeric))
);


--
-- Name: empleado_id_empleado_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.empleado_id_empleado_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: empleado_id_empleado_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.empleado_id_empleado_seq OWNED BY public.empleado.id_empleado;


--
-- Name: evento; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.evento (
    id_evento integer NOT NULL,
    nombre_evento character varying(100) NOT NULL,
    tipo_evento character varying(50),
    fecha_evento date NOT NULL,
    hora_inicio time without time zone NOT NULL,
    hora_fin time without time zone NOT NULL,
    cupo_maximo integer,
    organizador character varying(100),
    contacto character varying(30),
    descripcion text,
    id_cancha integer NOT NULL,
    CONSTRAINT chk_evento_horas CHECK ((hora_fin > hora_inicio)),
    CONSTRAINT evento_cupo_maximo_check CHECK ((cupo_maximo > 0))
);


--
-- Name: evento_id_evento_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.evento_id_evento_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: evento_id_evento_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.evento_id_evento_seq OWNED BY public.evento.id_evento;


--
-- Name: pago; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pago (
    id_pago integer NOT NULL,
    metodo_pago character varying(20) NOT NULL,
    comprobante character varying(100),
    estado_pago character varying(20) DEFAULT 'pendiente'::character varying NOT NULL,
    monto numeric(10,2) NOT NULL,
    fecha_pago timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    id_reserva integer NOT NULL,
    id_empleado integer,
    CONSTRAINT chk_pago_estado CHECK (((estado_pago)::text = ANY ((ARRAY['pendiente'::character varying, 'pagado'::character varying, 'reembolsado'::character varying])::text[]))),
    CONSTRAINT chk_pago_metodo CHECK (((metodo_pago)::text = ANY ((ARRAY['efectivo'::character varying, 'tarjeta'::character varying, 'transferencia'::character varying, 'qr'::character varying])::text[]))),
    CONSTRAINT pago_monto_check CHECK ((monto > (0)::numeric))
);


--
-- Name: pago_id_pago_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pago_id_pago_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pago_id_pago_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pago_id_pago_seq OWNED BY public.pago.id_pago;


--
-- Name: persona; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.persona (
    id_persona integer NOT NULL,
    nombre character varying(80) NOT NULL,
    apellido character varying(80) NOT NULL,
    ci character varying(20) NOT NULL,
    celular character varying(20),
    email character varying(120),
    CONSTRAINT chk_persona_email CHECK (((email IS NULL) OR ((email)::text ~~ '%@%'::text)))
);


--
-- Name: persona_id_persona_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.persona_id_persona_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: persona_id_persona_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.persona_id_persona_seq OWNED BY public.persona.id_persona;


--
-- Name: reserva; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reserva (
    id_reserva integer NOT NULL,
    fecha_reserva date NOT NULL,
    hora_inicio time without time zone NOT NULL,
    hora_fin time without time zone NOT NULL,
    duracion interval,
    fecha_creacion timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    estado_reserva character varying(20) DEFAULT 'pendiente'::character varying NOT NULL,
    motivo_cancelacion text,
    id_cliente integer NOT NULL,
    id_cancha integer NOT NULL,
    CONSTRAINT chk_reserva_estado CHECK (((estado_reserva)::text = ANY ((ARRAY['pendiente'::character varying, 'confirmada'::character varying, 'cancelada'::character varying, 'completada'::character varying])::text[]))),
    CONSTRAINT chk_reserva_horas CHECK ((hora_fin > hora_inicio))
);


--
-- Name: reserva_id_reserva_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.reserva_id_reserva_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: reserva_id_reserva_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.reserva_id_reserva_seq OWNED BY public.reserva.id_reserva;


--
-- Name: supervisa; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.supervisa (
    id_empleado integer NOT NULL,
    id_cancha integer NOT NULL,
    fecha_asignacion date DEFAULT CURRENT_DATE NOT NULL
);


--
-- Name: usuario; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuario (
    id_usuario integer NOT NULL,
    username character varying(50) NOT NULL,
    contrasena character varying(255) NOT NULL,
    rol character varying(20) NOT NULL,
    id_persona integer NOT NULL,
    CONSTRAINT chk_usuario_rol CHECK (((rol)::text = ANY ((ARRAY['cliente'::character varying, 'administrador'::character varying, 'empleado'::character varying])::text[])))
);


--
-- Name: usuario_id_usuario_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.usuario_id_usuario_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: usuario_id_usuario_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.usuario_id_usuario_seq OWNED BY public.usuario.id_usuario;


--
-- Name: administrador id_administrador; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.administrador ALTER COLUMN id_administrador SET DEFAULT nextval('public.administrador_id_administrador_seq'::regclass);


--
-- Name: cancha id_cancha; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cancha ALTER COLUMN id_cancha SET DEFAULT nextval('public.cancha_id_cancha_seq'::regclass);


--
-- Name: categoria id_categoria; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categoria ALTER COLUMN id_categoria SET DEFAULT nextval('public.categoria_id_categoria_seq'::regclass);


--
-- Name: cliente id_cliente; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cliente ALTER COLUMN id_cliente SET DEFAULT nextval('public.cliente_id_cliente_seq'::regclass);


--
-- Name: empleado id_empleado; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.empleado ALTER COLUMN id_empleado SET DEFAULT nextval('public.empleado_id_empleado_seq'::regclass);


--
-- Name: evento id_evento; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evento ALTER COLUMN id_evento SET DEFAULT nextval('public.evento_id_evento_seq'::regclass);


--
-- Name: pago id_pago; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pago ALTER COLUMN id_pago SET DEFAULT nextval('public.pago_id_pago_seq'::regclass);


--
-- Name: persona id_persona; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.persona ALTER COLUMN id_persona SET DEFAULT nextval('public.persona_id_persona_seq'::regclass);


--
-- Name: reserva id_reserva; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reserva ALTER COLUMN id_reserva SET DEFAULT nextval('public.reserva_id_reserva_seq'::regclass);


--
-- Name: usuario id_usuario; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario ALTER COLUMN id_usuario SET DEFAULT nextval('public.usuario_id_usuario_seq'::regclass);


--
-- Name: administrador administrador_id_usuario_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.administrador
    ADD CONSTRAINT administrador_id_usuario_key UNIQUE (id_usuario);


--
-- Name: administrador administrador_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.administrador
    ADD CONSTRAINT administrador_pkey PRIMARY KEY (id_administrador);


--
-- Name: cancha cancha_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cancha
    ADD CONSTRAINT cancha_pkey PRIMARY KEY (id_cancha);


--
-- Name: categoria categoria_nombre_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categoria
    ADD CONSTRAINT categoria_nombre_key UNIQUE (nombre);


--
-- Name: categoria categoria_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categoria
    ADD CONSTRAINT categoria_pkey PRIMARY KEY (id_categoria);


--
-- Name: cliente cliente_id_usuario_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cliente
    ADD CONSTRAINT cliente_id_usuario_key UNIQUE (id_usuario);


--
-- Name: cliente cliente_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cliente
    ADD CONSTRAINT cliente_pkey PRIMARY KEY (id_cliente);


--
-- Name: elige elige_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.elige
    ADD CONSTRAINT elige_pkey PRIMARY KEY (id_cliente, id_cancha);


--
-- Name: empleado empleado_id_usuario_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.empleado
    ADD CONSTRAINT empleado_id_usuario_key UNIQUE (id_usuario);


--
-- Name: empleado empleado_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.empleado
    ADD CONSTRAINT empleado_pkey PRIMARY KEY (id_empleado);


--
-- Name: evento evento_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evento
    ADD CONSTRAINT evento_pkey PRIMARY KEY (id_evento);


--
-- Name: pago pago_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pago
    ADD CONSTRAINT pago_pkey PRIMARY KEY (id_pago);


--
-- Name: persona persona_ci_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.persona
    ADD CONSTRAINT persona_ci_key UNIQUE (ci);


--
-- Name: persona persona_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.persona
    ADD CONSTRAINT persona_email_key UNIQUE (email);


--
-- Name: persona persona_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.persona
    ADD CONSTRAINT persona_pkey PRIMARY KEY (id_persona);


--
-- Name: reserva reserva_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reserva
    ADD CONSTRAINT reserva_pkey PRIMARY KEY (id_reserva);


--
-- Name: supervisa supervisa_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supervisa
    ADD CONSTRAINT supervisa_pkey PRIMARY KEY (id_empleado, id_cancha);


--
-- Name: usuario usuario_id_persona_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario
    ADD CONSTRAINT usuario_id_persona_key UNIQUE (id_persona);


--
-- Name: usuario usuario_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario
    ADD CONSTRAINT usuario_pkey PRIMARY KEY (id_usuario);


--
-- Name: usuario usuario_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario
    ADD CONSTRAINT usuario_username_key UNIQUE (username);


--
-- Name: idx_cancha_tipo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cancha_tipo ON public.cancha USING btree (tipo_deporte);


--
-- Name: idx_pago_reserva; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pago_reserva ON public.pago USING btree (id_reserva);


--
-- Name: idx_reserva_cliente; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reserva_cliente ON public.reserva USING btree (id_cliente);


--
-- Name: idx_reserva_fecha; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reserva_fecha ON public.reserva USING btree (fecha_reserva);


--
-- Name: ux_reserva_sin_choque; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_reserva_sin_choque ON public.reserva USING btree (id_cancha, fecha_reserva, hora_inicio) WHERE ((estado_reserva)::text <> 'cancelada'::text);


--
-- Name: administrador administrador_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.administrador
    ADD CONSTRAINT administrador_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario(id_usuario) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: cancha cancha_id_administrador_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cancha
    ADD CONSTRAINT cancha_id_administrador_fkey FOREIGN KEY (id_administrador) REFERENCES public.administrador(id_administrador) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: cancha cancha_id_categoria_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cancha
    ADD CONSTRAINT cancha_id_categoria_fkey FOREIGN KEY (id_categoria) REFERENCES public.categoria(id_categoria) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: cliente cliente_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cliente
    ADD CONSTRAINT cliente_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario(id_usuario) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: elige elige_id_cancha_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.elige
    ADD CONSTRAINT elige_id_cancha_fkey FOREIGN KEY (id_cancha) REFERENCES public.cancha(id_cancha) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: elige elige_id_cliente_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.elige
    ADD CONSTRAINT elige_id_cliente_fkey FOREIGN KEY (id_cliente) REFERENCES public.cliente(id_cliente) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: empleado empleado_id_administrador_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.empleado
    ADD CONSTRAINT empleado_id_administrador_fkey FOREIGN KEY (id_administrador) REFERENCES public.administrador(id_administrador) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: empleado empleado_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.empleado
    ADD CONSTRAINT empleado_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario(id_usuario) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: evento evento_id_cancha_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evento
    ADD CONSTRAINT evento_id_cancha_fkey FOREIGN KEY (id_cancha) REFERENCES public.cancha(id_cancha) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: pago pago_id_empleado_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pago
    ADD CONSTRAINT pago_id_empleado_fkey FOREIGN KEY (id_empleado) REFERENCES public.empleado(id_empleado) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: pago pago_id_reserva_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pago
    ADD CONSTRAINT pago_id_reserva_fkey FOREIGN KEY (id_reserva) REFERENCES public.reserva(id_reserva) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: reserva reserva_id_cancha_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reserva
    ADD CONSTRAINT reserva_id_cancha_fkey FOREIGN KEY (id_cancha) REFERENCES public.cancha(id_cancha) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: reserva reserva_id_cliente_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reserva
    ADD CONSTRAINT reserva_id_cliente_fkey FOREIGN KEY (id_cliente) REFERENCES public.cliente(id_cliente) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: supervisa supervisa_id_cancha_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supervisa
    ADD CONSTRAINT supervisa_id_cancha_fkey FOREIGN KEY (id_cancha) REFERENCES public.cancha(id_cancha) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: supervisa supervisa_id_empleado_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supervisa
    ADD CONSTRAINT supervisa_id_empleado_fkey FOREIGN KEY (id_empleado) REFERENCES public.empleado(id_empleado) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: usuario usuario_id_persona_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario
    ADD CONSTRAINT usuario_id_persona_fkey FOREIGN KEY (id_persona) REFERENCES public.persona(id_persona) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict FxtAANkAKCg7GBym9ipYbSc7F7o5OM4A1lviQ5ccO7iXmN9Vrpc7cFAa3Gd9jpj

