import React, { useCallback, useEffect, useState } from "react";
import { AppLayout } from "../components/layout/AppLayout";
import {
  notificacionesService,
  type Notificacion,
  type Plantilla,
  type EstadoNotificacion,
} from "../services/notificaciones";

type Pestana = "historial" | "plantillas";

const ESTADOS: { valor: EstadoNotificacion | ""; etiqueta: string }[] = [
  { valor: "", etiqueta: "Todos" },
  { valor: "pendiente", etiqueta: "Pendiente" },
  { valor: "enviado", etiqueta: "Enviado" },
  { valor: "fallido", etiqueta: "Fallido" },
];

const ETIQUETA_TIPO: Record<string, string> = {
  reserva_confirmada: "Reserva confirmada",
  reserva_modificada: "Reserva modificada",
  reserva_cancelada: "Reserva cancelada",
  recordatorio_reserva: "Recordatorio",
  nueva_reserva: "Aviso: nueva reserva",
  nueva_cancelacion: "Aviso: cancelación",
  nueva_modificacion: "Aviso: modificación",
};

const CAMPOS_PLANTILLA: {
  nombre: keyof Plantilla;
  etiqueta: string;
  requerido?: boolean;
  opciones?: string[];
  maxLength?: number;
}[] = [
  { nombre: "nombre", etiqueta: "Nombre", requerido: true, maxLength: 120 },
  { nombre: "codigo", etiqueta: "Código", requerido: true, maxLength: 60 },
  {
    nombre: "tipo_evento",
    etiqueta: "Disparador",
    requerido: true,
    opciones: Object.keys(ETIQUETA_TIPO),
  },
  { nombre: "canal", etiqueta: "Canal", opciones: ["email", "sms", "push"] },
  { nombre: "asunto", etiqueta: "Asunto", requerido: true, maxLength: 150 },
  { nombre: "cuerpo", etiqueta: "Cuerpo", requerido: true, maxLength: 2000 },
];

const ESTILO: React.CSSProperties = {
  padding: "12px 16px",
  backgroundColor: "var(--color-bg-elevated)",
  border: "1px solid var(--color-border)",
  borderRadius: "8px",
  marginBottom: "16px",
};

const etiquetaError = (e: unknown): string => {
  const err = e as { response?: { data?: { error?: string; detalle?: string } } };
  return err?.response?.data?.error || "Ocurrio un error.";
};

export default function NotificacionesPage() {
  const [pestana, setPestana] = useState<Pestana>("historial");
  const [notificaciones, setNotificaciones] = useState<Notificacion[]>([]);
  const [plantillas, setPlantillas] = useState<Plantilla[]>([]);
  const [estado, setEstado] = useState<EstadoNotificacion | "">("");
  const [detalle, setDetalle] = useState<Notificacion | null>(null);
  const [editando, setEditando] = useState<Plantilla | null>(null);
  const [formulario, setFormulario] = useState<Partial<Plantilla>>({});
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState("");

  const cargarHistorial = useCallback(async () => {
    setCargando(true);
    setError("");
    try {
      setNotificaciones(await notificacionesService.listar(estado || undefined));
    } catch (e) {
      setError(etiquetaError(e));
    } finally {
      setCargando(false);
    }
  }, [estado]);

  const cargarPlantillas = useCallback(async () => {
    setCargando(true);
    setError("");
    try {
      setPlantillas(await notificacionesService.listarPlantillas(true));
    } catch (e) {
      setError(etiquetaError(e));
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    if (pestana === "historial") void cargarHistorial();
    else void cargarPlantillas();
  }, [pestana, cargarHistorial, cargarPlantillas]);

  const ejecutar = async (accion: () => Promise<string>) => {
    setError("");
    setAviso("");
    setCargando(true);
    try {
      setAviso(await accion());
      if (pestana === "historial") await cargarHistorial();
      else await cargarPlantillas();
    } catch (e) {
      setError(etiquetaError(e));
    } finally {
      setCargando(false);
    }
  };

  const guardarPlantilla = async () => {
    // Un camporequired con espacios (" ") pasaba la validación porque " " es
    // truthy, y el backend guardaba la plantilla sin contenido útil.
    const faltan = CAMPOS_PLANTILLA.filter(
      (c) =>
        c.requerido &&
        (typeof formulario[c.nombre] !== "string"
          ? !formulario[c.nombre]
          : !formulario[c.nombre]?.toString().trim())
    );
    if (faltan.length) {
      setError(`Falta completar: ${faltan.map((c) => c.etiqueta).join(", ")}.`);
      return;
    }

    const codigo = (formulario.codigo || "").trim();
    if (!/^[A-Za-z0-9._-]{2,60}$/.test(codigo)) {
      setError(
        "El código debe tener entre 2 y 60 caracteres y solo letras, números, punto, guion o guion bajo."
      );
      return;
    }

    const limpio = Object.fromEntries(
      Object.entries(formulario).map(([k, v]) => [
        k,
        typeof v === "string" ? v.trim() : v,
      ])
    ) as Partial<Plantilla>;
    limpio.codigo = codigo;

    await ejecutar(async () => {
      if (editando) {
        await notificacionesService.actualizarPlantilla(editando.id_plantilla, limpio);
        return `Plantilla "${limpio.nombre}" actualizada.`;
      }
      await notificacionesService.crearPlantilla(limpio);
      return `Plantilla "${limpio.nombre}" creada.`;
    });
    setEditando(null);
    setFormulario({});
  };

  const abrirNueva = () => {
    setEditando(null);
    setFormulario({ canal: "email", tipo_evento: "reserva_confirmada", activa: true });
    setError("");
  };

  const abrirEdicion = (p: Plantilla) => {
    setEditando(p);
    setFormulario({ ...p });
    setError("");
  };

  const conteos = {
    pendiente: notificaciones.filter((n) => n.estado === "pendiente").length,
    fallido: notificaciones.filter((n) => n.estado === "fallido").length,
    enviado: notificaciones.filter((n) => n.estado === "enviado").length,
  };

  return (
    <AppLayout
      title="Notificaciones"
      subtitle="Avisos automaticos a clientes y administradores, con historial y reintentos"
    >
      <div className="header-row">
        <div className="tabs">
          <button
            className={pestana === "historial" ? "tab active" : "tab"}
            onClick={() => setPestana("historial")}
          >
            Historial ({notificaciones.length})
          </button>
          <button
            className={pestana === "plantillas" ? "tab active" : "tab"}
            onClick={() => setPestana("plantillas")}
          >
            Plantillas ({plantillas.length})
          </button>
        </div>

        {pestana === "historial" ? (
          <div className="acciones">
            <select
              value={estado}
              onChange={(e) => setEstado(e.target.value as EstadoNotificacion | "")}
            >
              {ESTADOS.map((s) => (
                <option key={s.valor} value={s.valor}>
                  {s.etiqueta}
                </option>
              ))}
            </select>
            <button
              className="btn-primary btn-sm"
              disabled={cargando}
              onClick={() =>
                ejecutar(async () => {
                  const r = await notificacionesService.enviarPendientes();
                  return `Pase de envio: ${r.enviadas} enviada(s), ${r.fallidas} fallida(s).`;
                })
              }
            >
              Enviar pendientes
            </button>
            <button
              className="btn-secondary btn-sm"
              disabled={cargando}
              onClick={() =>
                ejecutar(async () => {
                  const n = await notificacionesService.generarRecordatorios();
                  return `Recordatorios encolados: ${n}.`;
                })
              }
            >
              Generar recordatorios
            </button>
          </div>
        ) : (
          <button className="btn-success" onClick={abrirNueva}>
            + Nueva plantilla
          </button>
        )}
      </div>

      {error && <div className="mensaje error">{error}</div>}
      {aviso && <div className="mensaje exito">{aviso}</div>}

      {pestana === "historial" && (
        <>
          <div className="grid mid" style={{ marginBottom: "16px" }}>
            <div className="panel">
              <h3 style={{ marginTop: 0 }}>Pendientes</h3>
              <p style={{ fontSize: "28px", margin: 0, fontWeight: 700 }}>
                {conteos.pendiente}
              </p>
            </div>
            <div className="panel">
              <h3 style={{ marginTop: 0 }}>Enviadas</h3>
              <p style={{ fontSize: "28px", margin: 0, fontWeight: 700 }}>
                {conteos.enviado}
              </p>
            </div>
            <div className="panel">
              <h3 style={{ marginTop: 0 }}>Fallidas</h3>
              <p style={{ fontSize: "28px", margin: 0, fontWeight: 700 }}>
                {conteos.fallido}
              </p>
            </div>
          </div>

          {!cargando && notificaciones.length === 0 && (
            <div className="estado-vacio">
              No hay notificaciones en el historial.
            </div>
          )}

          {notificaciones.length > 0 && (
            <div className="tabla-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>Fecha</th>
                    <th>Tipo</th>
                    <th>Destinatario</th>
                    <th>Canal</th>
                    <th>Estado</th>
                    <th>Intentos</th>
                    <th>Asunto</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {notificaciones.map((n) => (
                    <tr key={n.id_notificacion}>
                      <td>
                        {n.fecha_creacion
                          ? new Date(n.fecha_creacion).toLocaleString("es")
                          : "-"}
                      </td>
                      <td>{ETIQUETA_TIPO[n.tipo] || n.tipo}</td>
                      <td>{n.destinatario}</td>
                      <td>{n.canal}</td>
                      <td>
                        <span className={`badge ${n.estado}`}>{n.estado}</span>
                      </td>
                      <td>
                        {n.intentos}/{n.max_intentos}
                      </td>
                      <td>{n.asunto}</td>
                      <td>
                        <button
                          className="btn-secondary btn-sm"
                          onClick={async () => {
                            try {
                              setDetalle(
                                await notificacionesService.detalle(n.id_notificacion)
                              );
                            } catch (e) {
                              setError(etiquetaError(e));
                            }
                          }}
                        >
                          Ver
                        </button>{" "}
                        {n.estado === "fallido" &&
                          n.intentos < n.max_intentos && (
                            <button
                              className="btn-primary btn-sm"
                              onClick={() =>
                                ejecutar(async () => {
                                  await notificacionesService.reintentar(
                                    n.id_notificacion
                                  );
                                  return "Notificacion reencolada.";
                                })
                              }
                            >
                              Reintentar
                            </button>
                          )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {pestana === "plantillas" && (
        <>
          {(editando || Object.keys(formulario).length > 0) && (
            <div style={ESTILO}>
              <h3 style={{ marginTop: 0 }}>
                {editando ? `Editar: ${editando.nombre}` : "Nueva plantilla"}
              </h3>
              {CAMPOS_PLANTILLA.map((campo) => (
                <div className="form-group" key={campo.nombre}>
                  <label>
                    {campo.etiqueta}
                    {campo.requerido ? " *" : ""}
                  </label>
                  {campo.opciones ? (
                    <select
                      value={(formulario[campo.nombre] as string) || ""}
                      onChange={(e) =>
                        setFormulario((f) => ({
                          ...f,
                          [campo.nombre]: e.target.value,
                        }))
                      }
                    >
                      <option value="">Selecciona...</option>
                      {campo.opciones.map((o) => (
                        <option key={o} value={o}>
                          {ETIQUETA_TIPO[o] || o}
                        </option>
                      ))}
                    </select>
                  ) : campo.nombre === "cuerpo" ? (
                    <textarea
                      rows={4}
                      value={formulario.cuerpo || ""}
                      onChange={(e) =>
                        setFormulario((f) => ({ ...f, cuerpo: e.target.value }))
                      }
                      maxLength={campo.maxLength}
                      placeholder="Usa {nombre_cliente}, {fecha_reserva}, {nombre_cancha}, {codigo_reserva}..."
                    />
                  ) : (
                    <input
                      type="text"
                      value={(formulario[campo.nombre] as string) || ""}
                      onChange={(e) =>
                        setFormulario((f) => ({
                          ...f,
                          [campo.nombre]: e.target.value,
                        }))
                      }
                      maxLength={campo.maxLength}
                      required={campo.requerido}
                    />
                  )}
                </div>
              ))}
              <div className="acciones">
                <button
                  className="btn-primary"
                  disabled={cargando}
                  onClick={guardarPlantilla}
                >
                  Guardar
                </button>
                <button
                  className="btn-secondary"
                  onClick={() => {
                    setEditando(null);
                    setFormulario({});
                  }}
                >
                  Cancelar
                </button>
              </div>
            </div>
          )}

          <div className="tabla-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Codigo</th>
                  <th>Nombre</th>
                  <th>Disparador</th>
                  <th>Canal</th>
                  <th>Activa</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {plantillas.map((p) => (
                  <tr key={p.id_plantilla}>
                    <td>
                      <code>{p.codigo}</code>
                    </td>
                    <td>{p.nombre}</td>
                    <td>{ETIQUETA_TIPO[p.tipo_evento] || p.tipo_evento}</td>
                    <td>{p.canal}</td>
                    <td>{p.activa ? "Si" : "No"}</td>
                    <td>
                      <button
                        className="btn-secondary btn-sm"
                        onClick={() => abrirEdicion(p)}
                      >
                        Editar
                      </button>{" "}
                      {editando?.id_plantilla === p.id_plantilla ? (
                        <button
                          className="btn-danger btn-sm"
                          onClick={() => {
                            setEditando(null);
                            setFormulario({});
                          }}
                        >
                          Cerrar
                        </button>
                      ) : (
                        <button
                          className="btn-danger btn-sm"
                          onClick={() => {
                            if (
                              window.confirm(
                                `¿Eliminar la plantilla "${p.nombre}"?`
                              )
                            ) {
                              void ejecutar(async () => {
                                await notificacionesService.eliminarPlantilla(
                                  p.id_plantilla
                                );
                                return `Plantilla "${p.nombre}" eliminada.`;
                              });
                            }
                          }}
                        >
                          Eliminar
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {detalle && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.45)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
          onClick={() => setDetalle(null)}
        >
          <div
            style={{
              background: "var(--color-bg)",
              padding: "20px",
              borderRadius: "8px",
              maxWidth: "640px",
              width: "90%",
              maxHeight: "85vh",
              overflowY: "auto",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <h3 style={{ margin: 0 }}>Notificacion #{detalle.id_notificacion}</h3>
              <button className="btn-secondary btn-sm" onClick={() => setDetalle(null)}>
                Cerrar
              </button>
            </div>
            <p>
              <b>Para:</b> {detalle.destinatario} · <b>Canal:</b> {detalle.canal} ·{" "}
              <span className={`badge ${detalle.estado}`}>{detalle.estado}</span>
            </p>
            <p>
              <b>Asunto:</b> {detalle.asunto}
            </p>
            <pre
              style={{
                whiteSpace: "pre-wrap",
                background: "var(--color-bg-elevated)",
                padding: "10px",
                borderRadius: "6px",
              }}
            >
              {detalle.cuerpo}
            </pre>
            {detalle.ultimo_error && (
              <p style={{ color: "#c62828" }}>
                <b>Ultimo error:</b> {detalle.ultimo_error}
              </p>
            )}
            {detalle.clave_idempotencia && (
              <p>
                <b>Clave:</b> <code>{detalle.clave_idempotencia}</code>
              </p>
            )}
            {detalle.historial && detalle.historial.length > 0 && (
              <>
                <h4>Historial de intentos</h4>
                <table>
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Estado</th>
                      <th>Detalle</th>
                      <th>Fecha</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detalle.historial.map((i) => (
                      <tr key={i.id_intento}>
                        <td>{i.numero_intento}</td>
                        <td>{i.estado}</td>
                        <td>{i.detalle}</td>
                        <td>
                          {i.fecha ? new Date(i.fecha).toLocaleString("es") : "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </div>
        </div>
      )}
    </AppLayout>
  );
}
