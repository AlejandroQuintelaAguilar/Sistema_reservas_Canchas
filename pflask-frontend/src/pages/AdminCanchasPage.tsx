import { useCallback, useEffect, useState } from "react";
import { AppLayout } from "../components/layout/AppLayout";
import { api } from "../services/api";
import {
  HORA_ATENCION_MAX,
  HORA_ATENCION_MIN,
  PRECIO_HORA_MAX,
  esNumeroValido,
  horaFinPosterior,
} from "../utils/validaciones";
import {
  DIAS,
  ETIQUETA_TIPO,
  FRANJAS_SUGERIDAS,
  tarifasService,
  type HistorialTarifa,
  type HorarioDia,
  type Tarifa,
  type TipoTarifa,
} from "../services/tarifasService";

interface Cancha {
  id: number;
  nombre: string;
  deporte: string;
  precio_hora: number;
  estado: string;
}

interface FormTarifa {
  tipo_tarifa: TipoTarifa;
  dia_semana: string;
  hora_inicio: string;
  hora_fin: string;
  precio_hora: string;
}

const FORM_VACIO: FormTarifa = {
  tipo_tarifa: "normal",
  dia_semana: "",
  hora_inicio: "06:00",
  hora_fin: "18:00",
  precio_hora: "",
};

const AdminCanchasPage = () => {
  const [canchas, setCanchas] = useState<Cancha[]>([]);
  const [seleccion, setSeleccion] = useState<number | null>(null);
  const [tarifas, setTarifas] = useState<Tarifa[]>([]);
  const [horarios, setHorarios] = useState<HorarioDia[]>([]);
  const [historial, setHistorial] = useState<HistorialTarifa[]>([]);
  const [borradorHorarios, setBorradorHorarios] = useState<HorarioDia[]>([]);

  const [form, setForm] = useState<FormTarifa>(FORM_VACIO);
  const [editando, setEditando] = useState<number | null>(null);
  const [verHistorial, setVerHistorial] = useState(false);

  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);

  const cancha = canchas.find((c) => c.id === seleccion) || null;

  const limpiarAvisos = () => {
    setMensaje("");
    setError("");
  };

  useEffect(() => {
    api
      .get<Cancha[]>("/canchas")
      .then(({ data }) => setCanchas(data))
      .catch(() => setError("No se pudo conectar con el backend. ¿Está corriendo Flask?"));
  }, []);

  const cargarTarifas = useCallback(async (idCancha: number) => {
    const [t, h, hist] = await Promise.all([
      tarifasService.listarCancha(idCancha),
      tarifasService.listarHorarios(idCancha),
      tarifasService.historial(idCancha),
    ]);
    setTarifas(t);
    setHorarios(h);
    setBorradorHorarios(h);
    setHistorial(hist);
  }, []);

  useEffect(() => {
    if (seleccion === null) return;
    limpiarAvisos();
    setEditando(null);
    setForm(FORM_VACIO);
    setVerHistorial(false);
    cargarTarifas(seleccion).catch((e) => setError(e.message));
  }, [seleccion, cargarTarifas]);

  // ---------------------------------------------------------------
  // Acciones de tarifa
  // ---------------------------------------------------------------
  const aplicarFranjaSugerida = (tipo: TipoTarifa) => {
    const [ini, fin] = FRANJAS_SUGERIDAS[tipo];
    setForm((f) => ({ ...f, tipo_tarifa: tipo, hora_inicio: ini, hora_fin: fin }));
  };

  const guardarTarifa = async (e: React.FormEvent) => {
    e.preventDefault();
    if (seleccion === null) return;
    limpiarAvisos();

    // Los atributos min/max del <input type="time"> acotan el rango, pero no la
    // coherencia: una tarifa 18:00-06:00 se descubría al guardar.
    if (!horaFinPosterior(form.hora_inicio, form.hora_fin)) {
      setError("La hora de fin debe ser posterior a la hora de inicio.");
      return;
    }
    if (!esNumeroValido(form.precio_hora, { min: 0.01, max: PRECIO_HORA_MAX })) {
      setError(
        `El precio por hora debe ser un número entre 0.01 y ${PRECIO_HORA_MAX}.`,
      );
      return;
    }
    // Una tarifa de fin de semana con dia_semana de un día laborable queda
    // guardada pero nunca se aplica. DIAS: Sábado=5, Domingo=6.
    if (form.tipo_tarifa === "fin_semana" && form.dia_semana !== "") {
      const dia = Number(form.dia_semana);
      if (dia !== 5 && dia !== 6) {
        setError("Una tarifa de fin de semana solo aplica a sábado o domingo.");
        return;
      }
    }

    setGuardando(true);
    try {
      const datos = {
        id_cancha: seleccion,
        tipo_tarifa: form.tipo_tarifa,
        dia_semana: form.dia_semana === "" ? null : Number(form.dia_semana),
        hora_inicio: form.hora_inicio,
        hora_fin: form.hora_fin,
        precio_hora: Number(form.precio_hora),
      };
      if (editando !== null) {
        await tarifasService.actualizar(editando, datos);
        setMensaje("Tarifa actualizada.");
      } else {
        await tarifasService.crear(datos);
        setMensaje("Tarifa creada.");
      }
      setEditando(null);
      setForm(FORM_VACIO);
      await cargarTarifas(seleccion);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setGuardando(false);
    }
  };

  const editar = (t: Tarifa) => {
    setEditando(t.id_tarifa);
    setVerHistorial(false);
    setForm({
      tipo_tarifa: t.tipo_tarifa,
      dia_semana: t.dia_semana === null ? "" : String(t.dia_semana),
      hora_inicio: t.hora_inicio,
      hora_fin: t.hora_fin,
      precio_hora: String(t.precio_hora),
    });
  };

  const alternarActivo = async (t: Tarifa) => {
    if (seleccion === null) return;
    limpiarAvisos();
    try {
      await tarifasService.actualizar(t.id_tarifa, { activo: !t.activo });
      setMensaje(t.activo ? "Tarifa desactivada." : "Tarifa activada.");
      await cargarTarifas(seleccion);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const eliminar = async (t: Tarifa) => {
    if (
      !window.confirm(
        `¿Eliminar la tarifa ${ETIQUETA_TIPO[t.tipo_tarifa]} ${t.hora_inicio}-${t.hora_fin}?`,
      )
    )
      return;
    if (seleccion === null) return;
    limpiarAvisos();
    try {
      await tarifasService.eliminar(t.id_tarifa);
      setMensaje("Tarifa eliminada.");
      if (editando === t.id_tarifa) {
        setEditando(null);
        setForm(FORM_VACIO);
      }
      await cargarTarifas(seleccion);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const eliminarTodas = async () => {
    if (!window.confirm("Se eliminarán TODAS las tarifas de esta cancha. ¿Continuar?")) return;
    if (seleccion === null) return;
    limpiarAvisos();
    try {
      await tarifasService.eliminarTodas(seleccion);
      setMensaje("Todas las tarifas fueron eliminadas.");
      setEditando(null);
      setForm(FORM_VACIO);
      await cargarTarifas(seleccion);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  // ---------------------------------------------------------------
  // Acciones de horario
  // ---------------------------------------------------------------
  const editarBorrador = (dia: number, campo: "hora_apertura" | "hora_cierre", valor: string) => {
    setBorradorHorarios((prev) =>
      prev.map((h) => (h.dia_semana === dia ? { ...h, [campo]: valor } : h)),
    );
  };

  const alternarDia = (dia: number) => {
    setBorradorHorarios((prev) =>
      prev.map((h) => (h.dia_semana === dia ? { ...h, activo: !h.activo } : h)),
    );
  };

  const guardarHorarios = async () => {
    if (seleccion === null) return;
    limpiarAvisos();

    // El botón está fuera de cualquier <form>, así que los atributos min/max de
    // la tabla nunca se aplican. Sin estas guardingas, un horario invertido hace
    // que el backend rechace todo el lote y se pierdan los 7 días de edición.
    for (const h of borradorHorarios) {
      if (!h.activo) continue;
      if (!h.hora_apertura || !h.hora_cierre) {
        setError(`Falta la hora de apertura o de cierre de ${DIAS[h.dia_semana] ?? `el día ${h.dia_semana}`}.`);
        return;
      }
      if (!horaFinPosterior(h.hora_apertura, h.hora_cierre)) {
        setError(
          `En ${DIAS[h.dia_semana] ?? `el día ${h.dia_semana}`} la hora de cierre debe ser posterior a la de apertura.`,
        );
        return;
      }
      if (h.hora_apertura < HORA_ATENCION_MIN || h.hora_cierre > HORA_ATENCION_MAX) {
        setError(
          `${DIAS[h.dia_semana] ?? `El día ${h.dia_semana}`} debe quedar dentro del horario de atención (${HORA_ATENCION_MIN} a ${HORA_ATENCION_MAX}).`,
        );
        return;
      }
    }

    setGuardando(true);
    try {
      const datos = borradorHorarios.map((h) => ({
        dia_semana: h.dia_semana,
        hora_apertura: h.hora_apertura,
        hora_cierre: h.hora_cierre,
        activo: h.activo,
      }));
      const nuevos = await tarifasService.guardarHorarios(seleccion, datos);
      setHorarios(nuevos);
      setBorradorHorarios(nuevos);
      setMensaje("Horarios guardados.");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setGuardando(false);
    }
  };

  const hayCambios =
    JSON.stringify(borradorHorarios.map((h) => [h.hora_apertura, h.hora_cierre, h.activo])) !==
    JSON.stringify(horarios.map((h) => [h.hora_apertura, h.hora_cierre, h.activo]));

  // ---------------------------------------------------------------
  return (
    <AppLayout
      title="Canchas, tarifas y horarios"
      subtitle="Define el precio por franja y el horario de atención de cada día"
    >
      {error && <div className="mensaje error">{error}</div>}
      {mensaje && <div className="mensaje success">{mensaje}</div>}

      <div className="form-card">
        <div className="section-title">1. Elige la cancha</div>
        {canchas.length === 0 ? (
          <p className="estado-vacio">No hay canchas registradas.</p>
        ) : (
          <div className="tabla-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Cancha</th>
                  <th>Deporte</th>
                  <th>Precio base</th>
                  <th>Estado</th>
                  <th>Tarifas</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {canchas.map((c) => (
                  <tr key={c.id} className={seleccion === c.id ? "sel" : undefined}>
                    <td>
                      <strong>{c.nombre}</strong>
                    </td>
                    <td>{c.deporte}</td>
                    <td>Bs {c.precio_hora}</td>
                    <td>
                      <span className={`badge ${c.estado}`}>{c.estado}</span>
                    </td>
                    <td>
                      {c.id === seleccion ? `${tarifas.length} configurada(s)` : "—"}
                    </td>
                    <td>
                      <button
                        className="btn-primary btn-sm"
                        onClick={() => setSeleccion(c.id)}
                        disabled={seleccion === c.id}
                      >
                        {seleccion === c.id ? "Seleccionada" : "Configurar"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {cancha && (
        <>
          <div className="form-card">
            <div className="section-title">2. Horarios por día — {cancha.nombre}</div>
            <p className="hora-hint">
              Si un día está desactivado la cancha no abre ese día. Un día sin
              configuración propia usa el horario general de la cancha (06:00 a 23:00).
            </p>
            <div className="tabla-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>Día</th>
                    <th>Apertura</th>
                    <th>Cierre</th>
                    <th>Abre</th>
                  </tr>
                </thead>
                <tbody>
                  {borradorHorarios.map((h) => (
                    <tr key={h.dia_semana}>
                      <td>
                        <strong>{h.dia_nombre}</strong>
                        {h.por_defecto && (
                          <span className="cancha-id"> (horario general)</span>
                        )}
                      </td>
                      <td>
                        <input
                          type="time"
                          min={HORA_ATENCION_MIN}
                          max={HORA_ATENCION_MAX}
                          disabled={!h.activo}
                          value={h.hora_apertura || ""}
                          onChange={(e) => editarBorrador(h.dia_semana, "hora_apertura", e.target.value)}
                        />
                      </td>
                      <td>
                        <input
                          type="time"
                          min={h.hora_apertura || HORA_ATENCION_MIN}
                          max={HORA_ATENCION_MAX}
                          disabled={!h.activo}
                          value={h.hora_cierre || ""}
                          onChange={(e) => editarBorrador(h.dia_semana, "hora_cierre", e.target.value)}
                        />
                      </td>
                      <td>
                        <label>
                          <input
                            type="checkbox"
                            checked={h.activo}
                            onChange={() => alternarDia(h.dia_semana)}
                          />{" "}
                          {h.activo ? "Sí" : "Cerrado"}
                        </label>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="acciones">
              <button
                type="button"
                className="btn-primary"
                onClick={guardarHorarios}
                disabled={!hayCambios || guardando}
              >
                {hayCambios ? "Guardar horarios" : "Sin cambios"}
              </button>
            </div>
          </div>

          <div className="form-card">
            <div className="section-title">3. Tarifas por franja</div>
            <p className="hora-hint">
              Prioridad: <strong>fin de semana</strong> &gt; <strong>nocturna</strong> &gt;{" "}
              <strong>normal</strong>. Si no defines tarifas se usa el precio base (Bs{" "}
              {cancha.precio_hora}). El monto se prorratea por hora al reservar y queda
              congelado en la reserva.
            </p>

            <div className="form-row">
              <button
                className="btn-secondary"
                onClick={() => aplicarFranjaSugerida("normal")}
                type="button"
              >
                Sugerir normal 06-18
              </button>
              <button
                className="btn-secondary"
                onClick={() => aplicarFranjaSugerida("nocturna")}
                type="button"
              >
                Sugerir nocturna 18-23
              </button>
              <button
                className="btn-secondary"
                onClick={() => aplicarFranjaSugerida("fin_semana")}
                type="button"
              >
                Sugerir fin de semana 06-23
              </button>
            </div>

            {tarifas.length === 0 ? (
              <p className="estado-vacio">
                Esta cancha no tiene tarifas: se cobra Bs {cancha.precio_hora} por hora.
              </p>
            ) : (
              <div className="tabla-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th>Tipo</th>
                      <th>Día</th>
                      <th>Franja</th>
                      <th>Precio/hora</th>
                      <th>Estado</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {tarifas.map((t) => (
                      <tr key={t.id_tarifa}>
                        <td>{ETIQUETA_TIPO[t.tipo_tarifa]}</td>
                        <td>{t.dia_nombre}</td>
                        <td>
                          {t.hora_inicio} – {t.hora_fin}
                        </td>
                        <td>Bs {t.precio_hora}</td>
                        <td>
                          <span className={`badge ${t.activo ? "disponible" : "fuera_servicio"}`}>
                            {t.activo ? "Activa" : "Inactiva"}
                          </span>
                        </td>
                        <td className="acciones">
                          <button className="btn-secondary btn-sm" onClick={() => editar(t)}>
                            Editar
                          </button>
                          <button className="btn-warning btn-sm" onClick={() => alternarActivo(t)}>
                            {t.activo ? "Desactivar" : "Activar"}
                          </button>
                          <button className="btn-danger btn-sm" onClick={() => eliminar(t)}>
                            Eliminar
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <div className="acciones">
              <button className="btn-danger btn-sm" onClick={eliminarTodas}>
                Eliminar todas
              </button>
              <button className="btn-secondary btn-sm" onClick={() => setVerHistorial((v) => !v)}>
                {verHistorial ? "Ocultar historial" : "Ver historial de cambios"}
              </button>
            </div>

            {verHistorial && (
              <div className="tabla-wrapper">
                {historial.length === 0 ? (
                  <p className="estado-vacio">Sin cambios registrados.</p>
                ) : (
                  <table>
                    <thead>
                      <tr>
                        <th>Fecha</th>
                        <th>Tipo</th>
                        <th>Día</th>
                        <th>Precio</th>
                        <th>Motivo</th>
                      </tr>
                    </thead>
                    <tbody>
                      {historial.map((h) => (
                        <tr key={h.id_historial}>
                          <td>{new Date(h.fecha).toLocaleString("es-BO")}</td>
                          <td>
                            {h.accion} —{" "}
                            {h.tipo_anterior
                              ? ETIQUETA_TIPO[h.tipo_anterior as TipoTarifa]
                              : "—"}{" "}
                            →{" "}
                            {h.tipo_nuevo ? ETIQUETA_TIPO[h.tipo_nuevo as TipoTarifa] : "eliminado"}
                          </td>
                          <td>
                            {h.dia_anterior_nombre ?? "Todos"} →{" "}
                            {h.dia_nuevo_nombre ?? "Todos"}
                          </td>
                          <td>
                            {h.precio_anterior ?? "—"} → {h.precio_nuevo ?? "—"}
                          </td>
                          <td>{h.motivo || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}

            <div className="divider" />

            <div className="section-title">
              {editando !== null ? "Editar tarifa" : "Nueva tarifa"}
            </div>
            <form onSubmit={guardarTarifa}>
              <div className="form-row">
                <div className="form-group">
                  <label>Tipo</label>
                  <select
                    value={form.tipo_tarifa}
                    onChange={(e) =>
                      setForm({ ...form, tipo_tarifa: e.target.value as TipoTarifa })
                    }
                  >
                    <option value="normal">Normal</option>
                    <option value="nocturna">Nocturna</option>
                    <option value="fin_semana">Fin de semana</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Día</label>
                  <select
                    value={form.dia_semana}
                    onChange={(e) => setForm({ ...form, dia_semana: e.target.value })}
                  >
                    <option value="">Todos los días</option>
                    {DIAS.map((d, i) => (
                      <option key={d} value={i}>
                        {d}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Hora inicio</label>
                  <input
                    type="time"
                    min="06:00"
                    max="23:00"
                    required
                    value={form.hora_inicio}
                    onChange={(e) => setForm({ ...form, hora_inicio: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label>Hora fin</label>
                  <input
                    type="time"
                    min="06:00"
                    max="23:00"
                    required
                    value={form.hora_fin}
                    onChange={(e) => setForm({ ...form, hora_fin: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label>Precio por hora (Bs)</label>
                  <input
                    type="number"
                    min="0.01"
                    max={PRECIO_HORA_MAX}
                    step="0.01"
                    required
                    value={form.precio_hora}
                    placeholder={String(cancha.precio_hora)}
                    onChange={(e) => setForm({ ...form, precio_hora: e.target.value })}
                  />
                </div>
              </div>
              {form.tipo_tarifa === "fin_semana" && form.dia_semana !== "" && (
                <div className="mensaje info">
                  El fin de semana solo aplica a sábado y domingo.
                </div>
              )}
              <div className="acciones">
                <button type="submit" className="btn-primary" disabled={guardando}>
                  {editando !== null ? "Guardar cambios" : "Crear tarifa"}
                </button>
                {editando !== null && (
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => {
                      setEditando(null);
                      setForm(FORM_VACIO);
                    }}
                  >
                    Cancelar
                  </button>
                )}
              </div>
            </form>
          </div>
        </>
      )}
    </AppLayout>
  );
};

export default AdminCanchasPage;
