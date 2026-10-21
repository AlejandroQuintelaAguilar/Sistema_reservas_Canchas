import { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import AppLayout from "../components/layout/AppLayout";
import { api } from "../services/api";
import { authService } from "../services/authService";
import {
  REQUISITOS_PASSWORD,
  erroresContrasena,
  validarFormularioUsuario,
  soloDigitos,
  soloDigitosCelular,
} from "../utils/validaciones";

const DIAS = ["L", "M", "X", "J", "V", "S", "D"];

const emptyForm = {
  nombre: "",
  apellido: "",
  ci: "",
  celular: "",
  email: "",
  username: "",
  password: "",
};

const DashboardPage = () => {
  const { user } = useAuth();
  const esAdmin = ["admin", "administrador"].includes(user?.role);

  const [eventos, setEventos] = useState([]);
  const [canchas, setCanchas] = useState([]);
  const [pagos, setPagos] = useState([]);
  const [users, setUsers] = useState([]);
  const [analitica, setAnalitica] = useState(null);
  const [cargando, setCargando] = useState(true);

  const [errorMsg, setErrorMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");
  const [editing, setEditing] = useState(null);
  const [agregando, setAgregando] = useState(false);
  const [tipoAlCrear, setTipoAlCrear] = useState("cliente");
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);

  // Cronómetro
  const [seconds, setSeconds] = useState(0);
  const [timerOn, setTimerOn] = useState(false);

  useEffect(() => {
    let interval = null;
    if (timerOn) {
      interval = setInterval(() => setSeconds((s) => s + 1), 1000);
    }
    return () => clearInterval(interval);
  }, [timerOn]);

  useEffect(() => {
    const cargarDatos = async () => {
      try {
        // /analitica es privado del administrador. Si se pidiera siempre, el
        // 403 de un cliente o empleado tumbaria todo el Promise.all y el
        // dashboard se quedaria vacio para esos roles.
        // /pagos tambien se restringe al administrador: un empleado o un
        // cliente no tienen por que ver la caja del complejo.
        const [ev, ca, pa] = await Promise.all([
          api.get("/eventos"),
          api.get("/canchas"),
          esAdmin ? api.get("/pagos") : Promise.resolve({ data: [] }),
        ]);
        setEventos(ev.data);
        setCanchas(ca.data);
        setPagos(pa.data || []);
        if (esAdmin) {
          try {
            const [an, u] = await Promise.all([
              api.get("/analitica"),
              authService.obtenerUsuarios(),
            ]);
            setAnalitica(an.data);
            setUsers(u);
          } catch (e) {
            /* sin permisos */
          }
        }
        setCargando(false);
      } catch (error) {
        setCargando(false);
      }
    };
    cargarDatos();
  }, [esAdmin]);

  const canchasDisponibles = canchas.filter(
    (c) => c.estado === "disponible",
  ).length;
  const canchasMantenimiento = canchas.filter(
    (c) => c.estado === "mantenimiento",
  ).length;
  const pagosConfirmados = pagos.filter(
    (p) => p.estado_pago === "pagado" || p.estado_pago === "confirmado",
  );
  const ingresos = pagosConfirmados.reduce(
    (acc, p) => acc + Number(p.monto || 0),
    0,
  );
  const pagosPendientes = pagos.filter(
    (p) => p.estado_pago === "pendiente",
  ).length;

  const proximos = [...eventos]
    .filter((e) => e.fecha_evento >= new Date().toISOString().slice(0, 10))
    .sort((a, b) => (a.fecha_evento > b.fecha_evento ? 1 : -1))
    .slice(0, 5);

  // Actividad semanal: cantidad de eventos por día de la semana
  const actividad = DIAS.map((dia, idx) => {
    const total = eventos.filter((e) => {
      const d = new Date(e.fecha_evento + "T00:00:00");
      return d.getDay() === ((idx + 1) % 7);
    }).length;
    return { day: dia, value: total };
  });
  const maxAct = Math.max(1, ...actividad.map((a) => a.value));

  // Donut: estados de canchas
  const totalCanchas = Math.max(1, canchas.length);
  const pctDisponible = Math.round(
    (canchasDisponibles / totalCanchas) * 100,
  );
  const pctMantenimiento = Math.round(
    (canchasMantenimiento / totalCanchas) * 100,
  );
  const pctOtro = 100 - pctDisponible - pctMantenimiento;

  // ---------- Analítica (vistas SQL) ----------
  const MESES_ES = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"];
  const ganancias = analitica?.ganancias_mensuales ?? [];
  const maxGanancia = Math.max(1, ...ganancias.map((g) => Number(g.ingresos) || 0));

  const empleados = analitica?.empleados ?? [];
  const maxRecaudado = Math.max(1, ...empleados.map((e) => Number(e.total_recaudado) || 0));

  const topCanchas = analitica?.top_canchas ?? [];
  const maxCancha = Math.max(1, ...topCanchas.map((c) => Number(c.reservas) || 0));

  const metodos = analitica?.pagos_por_metodo ?? [];
  const saldos = analitica?.saldos_clientes ?? [];
  const negativos = saldos.filter((s) => s.saldo_pendiente > 0);
  const totalPorCobrar = negativos.reduce((acc, s) => acc + Number(s.saldo_pendiente || 0), 0);

  const fmtMes = (m) => {
    const [y, mo] = String(m).split("-");
    return `${MESES_ES[Number(mo) - 1] || mo} ${String(y).slice(2)}`;
  };
  const fmtBs = (n) => "Bs " + Number(n || 0).toFixed(2);

  const fmt = (s) => {
    const h = String(Math.floor(s / 3600)).padStart(2, "0");
    const m = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
    const sec = String(s % 60).padStart(2, "0");
    return `${h}:${m}:${sec}`;
  };

  /* ---------- Gestión de usuarios (admin) ---------- */
  const handleEliminar = async (id) => {
    if (window.confirm("¿Estás seguro de que deseas eliminar este usuario?")) {
      try {
        await authService.eliminarUsuario(id);
        setUsers(users.filter((u) => u.id !== id));
        if (editing?.id === id) setEditing(null);
      } catch (error) {
        alert(error.response?.data?.error || "Error al eliminar el usuario.");
      }
    }
  };

  const handleEditar = (u) => {
    setErrorMsg("");
    setSuccessMsg("");
    setEditing(u);
    setForm({
      nombre: u.nombre || "",
      apellido: u.apellido || "",
      ci: u.ci || "",
      celular: u.celular || "",
      email: u.email || "",
      username: u.username || "",
      password: "",
    });
  };

  const handleAgregar = (tipo) => {
    setErrorMsg("");
    setSuccessMsg("");
    setEditing(null);
    setAgregando(true);
    setTipoAlCrear(tipo || "cliente");
    setForm(emptyForm);
  };

  const handleFormChange = (event) => {
    const { name, value } = event.target;
    // CI y celular son numericos: se filtran al escribir para no guardar letras.
    let limpio = value;
    if (name === "ci") limpio = soloDigitos(value);
    else if (name === "celular") limpio = soloDigitosCelular(value);
    setForm((prev) => ({ ...prev, [name]: limpio }));
  };

  const handleGuardar = async (event) => {
    event.preventDefault();
    if (editing) return handleActualizar(event);
    return handleCrear(event);
  };

  const handleActualizar = async (event) => {
    event.preventDefault();
    if (!editing) return;
    setSaving(true);
    setErrorMsg("");
    setSuccessMsg("");
    try {
      const payload = {
        nombre: form.nombre,
        apellido: form.apellido,
        ci: form.ci,
        celular: form.celular,
        email: form.email,
        username: form.username,
      };
      if (form.password.trim()) {
        // Al editar, cambiar la clave es opcional, pero si se escribe algo
        // tiene que cumplir la misma regla que en el registro.
        const errorPwd = erroresContrasena(form.password).join(" ");
        if (errorPwd) {
          setErrorMsg(`La contraseña no cumple la política: ${errorPwd}`);
          setSaving(false);
          return;
        }
        payload.password = form.password;
        payload.contrasena = form.password;
      }
      const updated = await authService.actualizarUsuario(editing.id, payload);
      setUsers(users.map((u) => (u.id === updated.id ? updated : u)));
      setSuccessMsg("Usuario actualizado correctamente.");
      setEditing(null);
      setAgregando(false);
      setForm(emptyForm);
    } catch (error) {
      setErrorMsg(error.response?.data?.error || "No se pudo actualizar.");
    } finally {
      setSaving(false);
    }
  };

  const handleCrear = async (event) => {
    event.preventDefault();
    setSaving(true);
    setErrorMsg("");
    setSuccessMsg("");

    // Antes esto hacia `return` en silencio: el usuario pulsaba Guardar y no
    // pasaba nada, sin saber que faltaba el nombre o el correo.
    const falla = validarFormularioUsuario(form, { passwordObligatoria: true });
    if (falla) {
      setErrorMsg(falla);
      setSaving(false);
      return;
    }

    try {
      const nuevo = await authService.crearUsuario({
        nombre: form.nombre,
        apellido: form.apellido,
        ci: form.ci,
        celular: form.celular,
        email: form.email,
        username: form.username,
        password: form.password,
      });
      const creado = nuevo?.user || nuevo;
      if (creado?.id && tipoAlCrear === "empleado") {
        await authService.actualizarUsuario(creado.id, { rol: "empleado" });
      }
      const lista = await authService.obtenerUsuarios();
      setUsers(lista);
      setSuccessMsg("Usuario creado correctamente.");
      setAgregando(false);
      setForm(emptyForm);
    } catch (error) {
      setErrorMsg(error.response?.data?.error || "No se pudo crear el usuario.");
    } finally {
      setSaving(false);
    }
  };

  // Los indicadores de caja solo son del administrador: el empleado registra
  // pagos, pero el total recaudado del complejo no le corresponde verlo.
  const stats = [
    {
      label: "Eventos totales",
      value: eventos.length,
      foot: "Próximos " + proximos.length,
      hero: true,
    },
    {
      label: "Canchas disponibles",
      value: canchasDisponibles,
      foot: canchasMantenimiento + " en mantenimiento",
    },
    ...(esAdmin
      ? [
          {
            label: "Pagos recibidos",
            value: pagosConfirmados.length,
            foot: pagosPendientes + " pendientes",
          },
          {
            label: "Ingresos",
            value: "Bs " + ingresos.toFixed(2),
            foot: "Confirmados",
          },
        ]
      : []),
  ];

  return (
    <AppLayout
      title="Dashboard"
      subtitle="Resumen general del complejo de canchas."
    >
      {cargando ? (
        <div className="cargando">Cargando datos...</div>
      ) : (
        <>
          {/* Tarjetas de estadísticas */}
          <div className="grid stats">
            {stats.map((s) => (
              <div className={`stat-card ${s.hero ? "hero" : ""}`} key={s.label}>
                <div className="stat-top">
                  <span>{s.label}</span>
                  <span>↗</span>
                </div>
                <div className="stat-num">{s.value}</div>
                <span className="stat-foot">{s.foot}</span>
              </div>
            ))}
          </div>

          <div className="grid mid">
            {/* Actividad semanal */}
            <div className="panel">
              <div className="panel-head">
                <h3>Actividad semanal</h3>
              </div>
              <div className="bars">
                {actividad.map((a, i) => (
                  <div className="bar-col" key={i}>
                    <div
                      className={`bar ${i === new Date().getDay() ? "active" : ""}`}
                      style={{ height: `${(a.value / maxAct) * 100}%` }}
                    />
                    <span>{a.day}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Próximos eventos */}
            <div className="panel">
              <h3>Próximos eventos</h3>
              <p className="hint">Servicios sociales y eventos</p>
              <div>
                {proximos.length === 0 ? (
                  <p className="hint">Sin eventos registrados.</p>
                ) : (
                  proximos.map((e) => (
                    <div className="task-row" key={e.id_evento}>
                      <span
                        className="dotcolor"
                        style={{ background: "var(--primary)" }}
                      />
                      <div>
                        <div>{e.nombre_evento}</div>
                        <div className="meta">
                          {e.fecha_evento} · {e.hora_inicio}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {esAdmin && (
              /* Recordatorios */
              <div className="panel">
                <div className="panel-head">
                  <h3>Recordatorios</h3>
                  <span className="hint" style={{ margin: 0 }}>
                    Pagos
                  </span>
                </div>
                <div>
                  {pagosPendientes === 0 ? (
                    <p className="hint">No hay pagos pendientes.</p>
                  ) : (
                    <div className="reminder-card">
                      <b>{pagosPendientes} pago(s) pendiente(s)</b>
                      <div className="reminder-time">
                        🕐 Revisar estado de pagos
                      </div>
                      <button
                        className="btn-start"
                        onClick={() => setSeconds(0)}
                      >
                        Marcar como revisado
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* ---------- PANELES ANALÍTICOS (vistas SQL) ---------- */}
          {esAdmin && (
            <>
          <div className="header-row" style={{ marginTop: "30px", marginBottom: "12px" }}>
            <h2>Analítica del complejo</h2>
            <span className="hint" style={{ margin: 0 }}>
              Vistas: ganancias, empleados, canchas, pagos y saldos
            </span>
          </div>

          <div className="grid mid">
            {/* Ganancias mensuales */}
            <div className="panel">
              <div className="panel-head">
                <h3>Ganancias por mes</h3>
                <span className="hint" style={{ margin: 0 }}>Ingresos</span>
              </div>
              <div className="bars" style={{ height: 160 }}>
                {ganancias.length === 0 ? (
                  <p className="hint">Sin datos.</p>
                ) : (
                  ganancias.map((g, i) => (
                    <div className="bar-col" key={i}>
                      <div className="bar-col-val">Bs {Number(g.ingresos).toFixed(0)}</div>
                      <div
                        className="bar"
                        style={{
                          height: `${(Number(g.ingresos) / maxGanancia) * 100}%`,
                        }}
                        title={`${fmtMes(g.mes)}: ${fmtBs(g.ingresos)}`}
                      />
                      <span>{fmtMes(g.mes)}</span>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Productividad de empleados */}
            <div className="panel">
              <div className="panel-head">
                <h3>Productividad de empleados</h3>
                <span className="hint" style={{ margin: 0 }}>Recaudado</span>
              </div>
              <div>
                {empleados.length === 0 ? (
                  <p className="hint">Sin datos.</p>
                ) : (
                  empleados.map((e) => (
                    <div className="hbar-row" key={e.nombre_empleado}>
                      <div className="hbar-label">
                        <span>{e.nombre_empleado}</span>
                        <b>{fmtBs(e.total_recaudado)}</b>
                      </div>
                      <div className="hbar-track">
                        <div
                          className="hbar-fill"
                          style={{
                            width: `${(Number(e.total_recaudado) / maxRecaudado) * 100}%`,
                            background: Number(e.por_cobrar) > 0 ? "var(--yellow)" : "var(--primary)",
                          }}
                        />
                      </div>
                      <div className="hbar-meta">
                        {e.pagos_procesados} pagos · {e.cargo}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Métodos de pago */}
            <div className="panel">
              <div className="panel-head">
                <h3>Métodos de pago</h3>
                <span className="hint" style={{ margin: 0 }}>Monto total</span>
              </div>
              <div>
                {metodos.length === 0 ? (
                  <p className="hint">Sin datos.</p>
                ) : (
                  metodos.map((m) => (
                    <div className="hbar-row" key={m.metodo_pago}>
                      <div className="hbar-label">
                        <span className="capitalize">{m.metodo_pago}</span>
                        <b>{fmtBs(m.total)}</b>
                      </div>
                      <div className="hbar-track">
                        <div
                          className="hbar-fill"
                          style={{
                            width: `${(Number(m.total) / Math.max(1, ...metodos.map((x) => Number(x.total)))) * 100}%`,
                            background: "var(--color-primary)",
                          }}
                        />
                      </div>
                      <div className="hbar-meta">{m.cantidad} pagos</div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          <div className="grid bottom" style={{ gridTemplateColumns: "1fr 1fr" }}>
            {/* Canchas más utilizadas */}
            <div className="panel">
              <div className="panel-head">
                <h3>Canchas más utilizadas</h3>
                <span className="hint" style={{ margin: 0 }}>Reservas</span>
              </div>
              <div>
                {topCanchas.length === 0 ? (
                  <p className="hint">Sin datos.</p>
                ) : (
                  topCanchas.slice(0, 6).map((c) => (
                    <div className="hbar-row" key={c.nombre_cancha}>
                      <div className="hbar-label">
                        <span>{c.nombre_cancha}</span>
                        <b>{c.reservas}</b>
                      </div>
                      <div className="hbar-track">
                        <div
                          className="hbar-fill"
                          style={{
                            width: `${(Number(c.reservas) / maxCancha) * 100}%`,
                            background: "var(--blue)",
                          }}
                        />
                      </div>
                      <div className="hbar-meta">{c.tipo_deporte}</div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Saldos por cobrar */}
            <div className="panel">
              <div className="panel-head">
                <h3>Por cobrar a clientes</h3>
                <span className="hint" style={{ margin: 0 }}>{fmtBs(totalPorCobrar)}</span>
              </div>
              <div>
                {negativos.length === 0 ? (
                  <p className="hint">Sin saldos pendientes.</p>
                ) : (
                  negativos.slice(0, 6).map((s) => (
                    <div className="hbar-row" key={s.nombre_cliente}>
                      <div className="hbar-label">
                        <span>{s.nombre_cliente}</span>
                        <b>{fmtBs(s.saldo_pendiente)}</b>
                      </div>
                      <div className="hbar-track">
                        <div
                          className="hbar-fill"
                          style={{
                            width: `${(Number(s.saldo_pendiente) / Math.max(1, ...negativos.map((x) => Number(x.saldo_pendiente)))) * 100}%`,
                            background: "var(--red)",
                          }}
                        />
                      </div>
                      <div className="hbar-meta">
                        pagado {fmtBs(s.total_pagado)} de {fmtBs(s.total_comprometido)}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
            </>
          )}

          <div className="grid bottom">
            {/* Lista de usuarios / equipo */}
            <div className="panel">
              <div className="panel-head">
                <h3>Usuarios del sistema</h3>
              </div>
              <div>
                {users.length === 0 && !esAdmin ? (
                  <p className="hint">
                    Solo el administrador puede ver la lista de usuarios.
                  </p>
                ) : users.length === 0 ? (
                  <p className="hint">Sin usuarios registrados.</p>
                ) : (
                  users.slice(0, 5).map((u) => (
                    <div className="member-row" key={u.id}>
                      <div className="m-avatar">
                        {(u.nombre?.[0] || u.username?.[0] || "U").toUpperCase()}
                      </div>
                      <div>
                        <div className="m-name">
                          {u.nombre} {u.apellido}
                        </div>
                        <div className="m-task">{u.username}</div>
                      </div>
                      <span
                        className={`status-pill ${
                          u.rol === "administrador"
                            ? "progress"
                            : u.rol === "empleado"
                              ? "pending"
                              : "completed"
                        }`}
                      >
                        {u.rol}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Progreso general (donut) */}
            <div className="panel">
              <h3>Estado de canchas</h3>
              <div className="donut-wrap">
                <div
                  className="donut"
                  id="donut"
                  style={{
                    background: `conic-gradient(var(--primary) 0% ${pctDisponible}%, var(--yellow) ${pctDisponible}% ${pctDisponible + pctMantenimiento}%, var(--border) ${pctDisponible + pctMantenimiento}% 100%)`,
                  }}
                >
                  <div className="donut-inner">{pctDisponible}%</div>
                </div>
                <div className="legend">
                  <span>
                    <i style={{ background: "var(--primary)" }}></i>
                    Disponibles
                  </span>
                  <span>
                    <i style={{ background: "var(--yellow)" }}></i>
                    Mantenimiento
                  </span>
                  <span>
                    <i style={{ background: "var(--border)" }}></i>
                    Otras
                  </span>
                </div>
              </div>
            </div>

            {esAdmin && (
              /* Cronómetro */
              <div className="tracker">
                <h3>Cronómetro</h3>
                <div className="tracker-time">{fmt(seconds)}</div>
                <div className="tracker-controls">
                  <button
                    className="tc-pause"
                    onClick={() => setTimerOn((t) => !t)}
                  >
                    {timerOn ? "❚❚" : "▶"}
                  </button>
                  <button
                    className="tc-stop"
                    onClick={() => {
                      setTimerOn(false);
                      setSeconds(0);
                    }}
                  >
                    ■
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* ---------- Gestión de usuarios (solo admin) ---------- */}
          {esAdmin && (
            <div
              id="gestion-usuarios"
              style={{
                marginTop: "30px",
                borderTop: "1px solid var(--color-border)",
                paddingTop: "10px",
              }}
            >
              <div className="header-row" style={{ marginBottom: "10px" }}>
                <h2>Gestión de Usuarios</h2>
                <div className="acciones">
                  <button
                    className="btn-primary btn-sm"
                    onClick={() => handleAgregar("cliente")}
                  >
                    + Agregar cliente
                  </button>
                  <button
                    className="btn-primary btn-sm"
                    onClick={() => handleAgregar("empleado")}
                  >
                    + Agregar empleado
                  </button>
                </div>
              </div>

              {errorMsg && (
                <div className="mensaje error">{errorMsg}</div>
              )}
              {successMsg && (
                <div className="mensaje success">{successMsg}</div>
              )}

              <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
                <div className="tabla-wrapper" style={{ margin: 0 }}>
                  <table>
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Nombre</th>
                        <th>Usuario</th>
                        <th>Correo</th>
                        <th>Rol</th>
                        <th>Acciones</th>
                      </tr>
                    </thead>
                    <tbody>
                      {users.length > 0 ? (
                        users.map((u) => (
                          <tr
                            key={u.id}
                            style={
                              editing?.id === u.id
                                ? { backgroundColor: "#ede9fe" }
                                : undefined
                            }
                          >
                            <td>{u.id}</td>
                            <td>
                              {u.nombre} {u.apellido}
                            </td>
                            <td>{u.username}</td>
                            <td>{u.email}</td>
                            <td>
                              <span
                                className={`status-pill ${
                                  u.rol === "administrador"
                                    ? "progress"
                                    : u.rol === "empleado"
                                      ? "pending"
                                      : "completed"
                                }`}
                              >
                                {u.rol}
                              </span>
                            </td>
                            <td>
                              <div className="acciones">
                                <button
                                  className="btn-primary btn-sm"
                                  onClick={() => handleEditar(u)}
                                >
                                  Editar
                                </button>
                                <button
                                  className="btn-danger btn-sm"
                                  onClick={() => handleEliminar(u.id)}
                                >
                                  Eliminar
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td
                            colSpan="6"
                            style={{ textAlign: "center", color: "var(--color-text-dim)" }}
                          >
                            No hay usuarios para mostrar.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {(editing || agregando) && (
                <div
                  className="modal-overlay"
                  onClick={() => {
                    setEditing(null);
                    setAgregando(false);
                    setForm(emptyForm);
                  }}
                >
                  <div
                    className="modal"
                    onClick={(e) => e.stopPropagation()}
                    style={{ maxWidth: "520px" }}
                  >
                  <form onSubmit={handleGuardar}>
                    <h3>
                      {editing
                        ? `Editar usuario #${editing.id}`
                        : `Agregar ${tipoAlCrear === "empleado" ? "empleado" : "cliente"}`}
                    </h3>
                  <div className="form-group">
                    <label>Nombre:</label>
                    <input
                      name="nombre"
                      value={form.nombre}
                      onChange={handleFormChange}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label>Apellido:</label>
                    <input
                      name="apellido"
                      value={form.apellido}
                      onChange={handleFormChange}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label>CI:</label>
                    <input
                      name="ci"
                      value={form.ci}
                      onChange={handleFormChange}
                      required
                      inputMode="numeric"
                      pattern="[0-9]{4,10}"
                      maxLength={10}
                      title="Entre 4 y 10 dígitos, sin letras."
                    />
                  </div>
                  <div className="form-group">
                    <label>Celular:</label>
                    <input
                      name="celular"
                      value={form.celular}
                      onChange={handleFormChange}
                      inputMode="tel"
                      pattern="\+?[0-9]{7,15}"
                      maxLength={16}
                      title="Entre 7 y 15 dígitos, con prefijo internacional opcional."
                    />
                  </div>
                  <div className="form-group">
                    <label>Correo:</label>
                    <input
                      type="email"
                      name="email"
                      value={form.email}
                      onChange={handleFormChange}
                    />
                  </div>
                  <div className="form-group">
                    <label>Username:</label>
                    <input
                      name="username"
                      value={form.username}
                      onChange={handleFormChange}
                      required
                      minLength={4}
                      maxLength={30}
                      pattern="[A-Za-z0-9._\-]{4,30}"
                      title="Entre 4 y 30 caracteres: letras, números, punto, guion o guion bajo."
                    />
                  </div>
                  <div className="form-group">
                    <label>Contraseña {agregando ? "" : "(opcional):"}</label>
                    <input
                      type="password"
                      name="password"
                      value={form.password}
                      onChange={handleFormChange}
                      placeholder={
                        agregando
                          ? "Define la contraseña del nuevo usuario"
                          : "Dejar vacío para no cambiarla"
                      }
                      autoComplete="new-password"
                      required={agregando}
                      minLength={agregando ? 8 : undefined}
                      maxLength={128}
                    />
                    {agregando && (
                      <small className="hint">{REQUISITOS_PASSWORD}</small>
                    )}
                  </div>
                  <div className="modal-actions">
                    <button type="submit" className="btn-primary" disabled={saving}>
                      {saving
                        ? "Guardando..."
                        : editing
                          ? "Guardar cambios"
                          : `Crear ${tipoAlCrear === "empleado" ? "empleado" : "cliente"}`}
                    </button>
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() => {
                        setEditing(null);
                        setAgregando(false);
                        setForm(emptyForm);
                      }}
                    >
                      Cancelar
                    </button>
                  </div>
                  </form>
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </AppLayout>
  );
};

export default DashboardPage;