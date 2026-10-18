import { useCallback, useEffect, useMemo, useState } from "react";
import AppLayout from "../components/layout/AppLayout";
import { useAuth } from "../context/AuthContext";
import { cajaService, pagosService } from "../services/pagos";
import Modal from "../components/common/Modal";
import {
  MONTO_MAX,
  aNumero,
  esNumeroValido,
  textoVacio,
} from "../utils/validaciones";
import type {
  Arqueo,
  DevolucionSolicitud,
  Pago,
  PagoAuditoria,
  ReservaParaPago,
  TurnoCaja,
} from "../services/pagos";

type Pestana = "pagos" | "caja" | "devoluciones" | "auditoria";

const METODOS = [
  { value: "efectivo", label: "Efectivo" },
  { value: "qr", label: "QR" },
  { value: "transferencia", label: "Transferencia" },
  { value: "tarjeta", label: "Tarjeta" },
];

const FILTROS = [
  { valor: "", etiqueta: "Todos" },
  { valor: "pendiente", etiqueta: "Pendiente" },
  { valor: "pendiente_validacion", etiqueta: "Por validar" },
  { valor: "aprobado", etiqueta: "Aprobado" },
  { valor: "rechazado", etiqueta: "Rechazado" },
  { valor: "expirado", etiqueta: "Expirado" },
  { valor: "devuelto", etiqueta: "Devuelto" },
];

const bs = (valor: number | null | undefined) =>
  `Bs ${Number(valor || 0).toLocaleString("es-BO", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;

const fechaCorta = (valor: string | null | undefined) =>
  valor ? new Date(valor).toLocaleString("es-BO", { dateStyle: "short", timeStyle: "short" }) : "-";

const PagosPage = () => {
  const { user } = useAuth();
  const esAdmin = user?.role === "admin" || user?.role === "administrador";
  const esOperacion = esAdmin || user?.role === "empleado";
  // El administrador no siempre tiene ficha de empleado: sin ella no hay caja.
  const tieneEmpleado = Boolean(user?.id_empleado);

  const [pestana, setPestana] = useState<Pestana>("pagos");

  const [pagos, setPagos] = useState<Pago[]>([]);
  const [reservas, setReservas] = useState<ReservaParaPago[]>([]);
  const [filtro, setFiltro] = useState("");
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const [turno, setTurno] = useState<Partial<TurnoCaja> | null>(null);
  const [arqueo, setArqueo] = useState<Arqueo | null>(null);
  const [turnos, setTurnos] = useState<TurnoCaja[]>([]);

  const [devoluciones, setDevoluciones] = useState<DevolucionSolicitud[]>([]);
  const [auditorias, setAuditorias] = useState<PagoAuditoria[]>([]);

  // --- Registro de pago ---------------------------------------------------
  const [mostrarForm, setMostrarForm] = useState(false);
  const [form, setForm] = useState({
    id_reserva: "",
    metodo_pago: "efectivo",
    monto: "",
    id_empleado: "",
  });

  // --- Acciones sobre un pago -------------------------------------------
  const [motivoRechazo, setMotivoRechazo] = useState<Record<number, string>>({});
  const [mostrarRechazo, setMostrarRechazo] = useState<number | null>(null);

  // Formularios que reemplazan los window.prompt: permiten type, min, step y
  // validación en línea, y de paso el mensaje de error se ve dentro de la app.
  const [cierreFisico, setCierreFisico] = useState("");
  const [cierreObservacion, setCierreObservacion] = useState("");
  const [mostrarCierre, setMostrarCierre] = useState(false);
  const [auditoriaPago, setAuditoriaPago] = useState<Pago | null>(null);
  const [auditoriaMonto, setAuditoriaMonto] = useState("");
  const [auditoriaReferencia, setAuditoriaReferencia] = useState("");
  const [devolucionAbierta, setDevolucionAbierta] = useState<DevolucionSolicitud | null>(null);
  const [devolucionMotivo, setDevolucionMotivo] = useState("");
  const [observacionAprobar, setObservacionAprobar] = useState<Record<number, string>>({});

  const cargar = useCallback(
    async (estado = filtro) => {
      setCargando(true);
      setError("");
      try {
        setPagos(await pagosService.listar({ estado: estado || undefined, detalle: true }));
      } catch (e: any) {
        setError(e.response?.data?.error || "No se pudieron cargar los pagos.");
      } finally {
        setCargando(false);
      }
    },
    [filtro],
  );

  useEffect(() => {
    cargar("");
    pagosService
      .listarReservasParaPago()
      .then(setReservas)
      .catch(() => setReservas([]));
  }, [cargar]);

  const cargarCaja = useCallback(async () => {
    try {
      const actual = await cajaService.turnoActual();
      setTurno(actual && actual.id_turno ? actual : null);
      setTurnos(await cajaService.listarTurnos());
      if (actual && actual.id_turno) {
        setArqueo(await cajaService.arqueo(actual.id_turno));
      } else {
        setArqueo(null);
      }
    } catch (e: any) {
      setError(e.response?.data?.error || "No se pudo cargar la caja.");
    }
  }, []);

  const cargarDevoluciones = useCallback(async () => {
    try {
      setDevoluciones(await pagosService.listarDevoluciones());
    } catch (e: any) {
      setError(e.response?.data?.error || "No se pudieron cargar las devoluciones.");
    }
  }, []);

  const cargarAuditorias = useCallback(async () => {
    try {
      setAuditorias(await pagosService.listarAuditorias());
    } catch (e: any) {
      setError(e.response?.data?.error || "No se pudieron cargar las auditorías.");
    }
  }, []);

  useEffect(() => {
    if (pestana === "caja") cargarCaja();
    if (pestana === "devoluciones") cargarDevoluciones();
    if (pestana === "auditoria" && esAdmin) cargarAuditorias();
  }, [pestana, cargarCaja, cargarDevoluciones, cargarAuditorias, esAdmin]);

  const ejecutar = async (accion: () => Promise<any>, texto: string) => {
    setOcupado(true);
    setError("");
    setMensaje("");
    try {
      const respuesta = await accion();
      setMensaje(respuesta?.mensaje || texto);
      return respuesta;
    } catch (e: any) {
      setError(e.response?.data?.error || e.message || "No se pudo completar la operación.");
      return null;
    } finally {
      setOcupado(false);
    }
  };

  // --- Totales del resumen ------------------------------------------------
  const resumen = useMemo(() => {
    const aprobado = pagos.filter((p) => p.estado_pago === "aprobado");
    const devuelto = pagos
      .filter((p) => p.estado_pago === "aprobado" || p.estado_pago === "devuelto")
      .reduce((acc, p) => acc + Number(p.monto_devuelto || 0), 0);
    return {
      aprovados: aprobado.length,
      cobrado: aprobado.reduce((acc, p) => acc + Number(p.monto || 0), 0),
      porValidar: pagos.filter((p) => p.estado_pago === "pendiente_validacion").length,
      devuelto,
    };
  }, [pagos]);

  const seleccionarReserva = (id: string) => {
    const reserva = reservas.find((r) => String(r.id_reserva) === id);
    setForm((f) => ({
      ...f,
      id_reserva: id,
      monto: reserva ? String(reserva.saldo_pendiente ?? "") : f.monto,
    }));
  };

  const guardar = async (ev: React.FormEvent) => {
    ev.preventDefault();

    // El backend rechaza el monto si supera el saldo, pero solo después del
    // viaje: se comprueba aquí para no mandar un formulario inútil.
    const monto = aNumero(form.monto);
    if (!esNumeroValido(monto, { min: 0.01, max: MONTO_MAX })) {
      setError(`El monto debe ser un número mayor que 0 y hasta ${MONTO_MAX}.`);
      return;
    }
    const idReserva = aNumero(form.id_reserva);
    if (!idReserva) {
      setError("Selecciona la reserva a la que aplicar el pago.");
      return;
    }
    const saldo = reservas.find((r) => String(r.id_reserva) === form.id_reserva)?.saldo_pendiente;
    if (saldo != null && (monto as number) > Number(saldo)) {
      setError(
        `El monto supera el saldo pendiente de la reserva (Bs ${bs(Number(saldo))}).`,
      );
      return;
    }

    const datos: {
      id_reserva: number;
      monto: number;
      id_empleado?: number;
    } = {
      id_reserva: idReserva,
      monto: monto as number,
    };
    if (form.metodo_pago === "efectivo" && esAdmin && form.id_empleado) {
      datos.id_empleado = Number(form.id_empleado);
    }
    const ok = await ejecutar(
      () => pagosService.registrarEfectivo(datos),
      "Pago en efectivo registrado.",
    );
    if (ok) {
      setMostrarForm(false);
      setForm({ id_reserva: "", metodo_pago: "efectivo", monto: "", id_empleado: "" });
      await cargar();
    }
  };

  const aprobar = async (pago: Pago) => {
    const ok = await ejecutar(
      () =>
        pagosService.aprobar(pago.id_pago, observacionAprobar[pago.id_pago] || undefined),
      `Pago #${pago.id_pago} aprobado.`,
    );
    if (ok) {
      setObservacionAprobar((o) => ({ ...o, [pago.id_pago]: "" }));
      await cargar();
    }
  };

  const rechazar = async (pago: Pago) => {
    const motivo = (motivoRechazo[pago.id_pago] || "").trim();
    if (!motivo) {
      setError("Escribe el motivo del rechazo.");
      return;
    }
    const ok = await ejecutar(
      () => pagosService.rechazar(pago.id_pago, motivo),
      `Pago #${pago.id_pago} rechazado.`,
    );
    if (ok) {
      setMostrarRechazo(null);
      setMotivoRechazo((m) => ({ ...m, [pago.id_pago]: "" }));
      await cargar();
    }
  };

  const abrirTurno = async () => {
    const ok = await ejecutar(() => cajaService.abrirTurno(), "Turno de caja abierto.");
    if (ok) await cargarCaja();
  };

  const cerrarTurno = async () => {
    // Antes era un window.prompt: el prompt no admite type ni min, así que un
    // "abc" se convertía en Number("abc") = NaN y NaN > 0.009 da false. El
    // descuadre nunca promptingaba observación y el turno se cerraba con el
    // monto en null. Ahora el monto se pide en un formulario con validación.
    if (!turno?.id_turno) return;
    const esperado = Number(arqueo?.monto_esperado_efectivo ?? 0);
    const fisico = String(cierreFisico).trim();

    if (!esNumeroValido(fisico, { min: 0, max: MONTO_MAX })) {
      setError(`El efectivo contado en caja debe ser un número entre 0 y ${MONTO_MAX}.`);
      return;
    }

    const monto = Number(fisico);
    const descuadra = Math.abs(monto - esperado) > 0.009;
    if (descuadra && textoVacio(cierreObservacion)) {
      setError(
        `El monto no coincide con el esperado (Bs ${bs(esperado)}). Explica la diferencia.`,
      );
      return;
    }

    const ok = await ejecutar(
      () => cajaService.cerrarTurno(turno.id_turno as number, monto, cierreObservacion.trim()),
      "Turno de caja cerrado.",
    );
    if (ok) {
      setCierreFisico("");
      setCierreObservacion("");
      await cargarCaja();
    }
  };

  const confirmarCierre = async (e: React.FormEvent) => {
    e.preventDefault();
    await cerrarTurno();
  };

  const decidirDevolucion = async (
    solicitud: DevolucionSolicitud,
    accion: "aprobar" | "rechazar",
  ) => {
    // Rechazar exige motivo: antes se mandaba el texto del prompt tal cual,
    // incluso vacío, y el backend respondía 400 sin explicación.
    if (accion === "rechazar" && textoVacio(devolucionMotivo)) {
      setError("Escribe el motivo del rechazo de la devolución.");
      return;
    }
    const motivo = textoVacio(devolucionMotivo) ? undefined : devolucionMotivo.trim();
    const ok = await ejecutar(
      () =>
        accion === "aprobar"
          ? pagosService.aprobarDevolucion(solicitud.id_solicitud)
          : pagosService.rechazarDevolucion(solicitud.id_solicitud, motivo || ""),
      `Devolución ${accion === "aprobar" ? "aprobada" : "rechazada"}.`,
    );
    if (ok) {
      setDevolucionMotivo("");
      setDevolucionAbierta(null);
      await cargarDevoluciones();
      await cargar();
    }
  };

  const auditar = async (pago: Pago) => {
    const monto = String(auditoriaMonto).trim();
    if (!esNumeroValido(monto, { min: 0.01, max: MONTO_MAX })) {
      setError(`El monto del comprobante debe ser un número mayor que 0 y hasta ${MONTO_MAX}.`);
      return;
    }
    const ok = await ejecutar(
      () =>
        pagosService.auditar(pago.id_pago, {
          monto_comprobante: Number(monto),
          metodo_comprobante: pago.metodo_pago,
          referencia_comprobante: auditoriaReferencia.trim() || undefined,
        }),
      "Auditoría registrada.",
    );
    if (ok) {
      setAuditoriaMonto("");
      setAuditoriaReferencia("");
      setAuditoriaPago(null);
      await cargarAuditorias();
      await cargar();
    }
  };

  const descargarRecibo = async (pago: Pago) => {
    await ejecutar(() => pagosService.descargarRecibo(pago.id_pago), "Recibo descargado.");
  };

  const Pestanas: { valor: Pestana; etiqueta: string; soloAdmin?: boolean }[] = [
    { valor: "pagos", etiqueta: "Pagos" },
    { valor: "caja", etiqueta: "Caja y arqueo" },
    { valor: "devoluciones", etiqueta: "Devoluciones" },
    { valor: "auditoria", etiqueta: "Auditoría", soloAdmin: true },
  ];

  return (
    <AppLayout
      title={pestana === "caja" ? "Caja y arqueo" : "Gestión de Pagos"}
      subtitle={
        pestana === "caja"
          ? "Abre tu turno, registra el efectivo y cierra con el arqueo"
          : "Validación de comprobantes, caja y devoluciones"
      }
    >
      <div className="panel" style={{ marginBottom: "20px" }}>
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          {Pestanas.filter((p) => !p.soloAdmin || esAdmin).map((p) => (
            <button
              key={p.valor}
              className={pestana === p.valor ? "btn-primary btn-sm" : "btn-secondary btn-sm"}
              onClick={() => setPestana(p.valor)}
            >
              {p.etiqueta}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="mensaje error">{error}</div>}
      {mensaje && <div className="mensaje success">{mensaje}</div>}

      {/* ================= PAGOS ================= */}
      {pestana === "pagos" && (
        <>
          <div className="panel" style={{ marginBottom: "20px" }}>
            <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
              {FILTROS.map((f) => (
                <button
                  key={f.valor}
                  className={filtro === f.valor ? "btn-primary btn-sm" : "btn-secondary btn-sm"}
                  onClick={() => {
                    setFiltro(f.valor);
                    cargar(f.valor);
                  }}
                >
                  {f.etiqueta}
                </button>
              ))}
            </div>
          </div>

          <div className="grid mid" style={{ marginBottom: "20px" }}>
            <div className="panel">
              <h3>Aprobados</h3>
              <div className="big-number">{resumen.aprovados}</div>
            </div>
            <div className="panel">
              <h3>Cobrado</h3>
              <div className="big-number">{bs(resumen.cobrado)}</div>
            </div>
            <div className="panel">
              <h3>Por validar</h3>
              <div className="big-number">{resumen.porValidar}</div>
            </div>
            <div className="panel">
              <h3>Devuelto</h3>
              <div className="big-number">{bs(resumen.devuelto)}</div>
            </div>
          </div>

          {esOperacion && (
            <div className="panel" style={{ marginBottom: "20px" }}>
              <div className="panel-head">
                <h3>Registrar pago en ventanilla</h3>
                <span className="hint" style={{ margin: 0 }}>
                  El efectivo se aprueba al instante
                </span>
              </div>
              <button className="btn-success btn-sm" onClick={() => setMostrarForm((v) => !v)}>
                {mostrarForm ? "Cerrar" : "➕ Registrar pago"}
              </button>

              {mostrarForm && (
                <form onSubmit={guardar} style={{ marginTop: "16px" }}>
                  <div className="form-row">
                    <div className="form-group">
                      <label>Reserva con saldo</label>
                      <select
                        required
                        value={form.id_reserva}
                        onChange={(e) => seleccionarReserva(e.target.value)}
                      >
                        <option value="">Selecciona una reserva</option>
                        {reservas.map((r) => (
                          <option key={r.id_reserva} value={r.id_reserva}>
                            #{r.id_reserva} · {r.cancha} · {r.cliente} · saldo {bs(r.saldo_pendiente)}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="form-group">
                      <label>Método de pago</label>
                      <select
                        value={form.metodo_pago}
                        onChange={(e) => setForm({ ...form, metodo_pago: e.target.value })}
                      >
                        {METODOS.map((m) => (
                          <option key={m.value} value={m.value}>
                            {m.label}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="form-group">
                      <label>Monto (Bs)</label>
                      <input
                        type="number"
                        step="0.01"
                        min="0.01"
                        max={MONTO_MAX}
                        required
                        value={form.monto}
                        onChange={(e) => setForm({ ...form, monto: e.target.value })}
                      />
                      {(() => {
                        const saldo = reservas.find(
                          (r) => String(r.id_reserva) === form.id_reserva,
                        )?.saldo_pendiente;
                        const monto = aNumero(form.monto);
                        if (saldo == null || monto == null) return null;
                        if (monto > Number(saldo)) {
                          return (
                            <small className="hint" style={{ color: "var(--color-danger)" }}>
                              Supera el saldo pendiente ({bs(Number(saldo))}).
                            </small>
                          );
                        }
                        return null;
                      })()}
                    </div>
                    {esAdmin && (
                      <div className="form-group">
                        <label>Empleado que recibe</label>
                        <input
                          type="number"
                          min="1"
                          step="1"
                          placeholder="id_empleado"
                          value={form.id_empleado}
                          onChange={(e) => setForm({ ...form, id_empleado: e.target.value })}
                        />
                      </div>
                    )}
                  </div>
                  <button type="submit" className="btn-primary" disabled={ocupado}>
                    {ocupado ? "Guardando..." : "Registrar pago"}
                  </button>
                </form>
              )}
            </div>
          )}

          {cargando ? (
            <div className="estado-vacio">Cargando pagos...</div>
          ) : pagos.length === 0 ? (
            <div className="estado-vacio">📭 No hay pagos {filtro ? `en estado ${filtro}` : "registrados"}.</div>
          ) : (
            <div className="panel">
              <div className="panel-head">
                <h3>Listado de pagos</h3>
                <span className="hint" style={{ margin: 0 }}>
                  {pagos.length} registro(s)
                </span>
              </div>
              <div className="tabla-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Reserva</th>
                      <th>Cliente / Cancha</th>
                      <th>Fecha</th>
                      <th>Método</th>
                      <th>Monto</th>
                      <th>Comprobante</th>
                      <th>Estado</th>
                      <th>Acciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pagos.map((p) => (
                      <tr key={p.id_pago}>
                        <td>{p.id_pago}</td>
                        <td>
                          #{p.id_reserva}
                          {p.reserva?.estado_reserva && (
                            <div className="hint">
                              {p.reserva.fecha_reserva?.slice(0, 10)}
                              {p.reserva.hora_inicio ? ` · ${p.reserva.hora_inicio.slice(0, 5)}` : ""}
                              {" · "}
                              {p.reserva.estado_reserva}
                            </div>
                          )}
                          {typeof p.saldo_reserva === "number" && (
                            <div className="hint">Saldo reserva: {bs(p.saldo_reserva)}</div>
                          )}
                        </td>
                        <td>
                          {p.reserva?.cliente || "-"}
                          {p.reserva?.cancha && <div className="hint">{p.reserva.cancha}</div>}
                        </td>
                        <td>{fechaCorta(p.fecha_pago)}</td>
                        <td className="capitalize">{p.metodo_pago}</td>
                        <td>
                          {bs(p.monto)}
                          {Number(p.monto_devuelto) > 0 && (
                            <div className="hint">Devuelto: {bs(p.monto_devuelto)}</div>
                          )}
                        </td>
                        <td>
                          {p.comprobante ? (
                            <>
                              <div>{p.nombre_original || "adjunto"}</div>
                              <div className="hint">{p.referencia || "sin referencia"}</div>
                            </>
                          ) : (
                            <span className="hint">sin comprobante</span>
                          )}
                        </td>
                        <td>
                          <span className={`badge ${p.estado_pago}`}>{p.estado_label}</span>
                          {p.motivo_rechazo && <div className="hint">{p.motivo_rechazo}</div>}
                        </td>
                        <td>
                          <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                            {esOperacion && p.estado_pago === "pendiente_validacion" && (
                              <>
                                <button
                                  className="btn-success btn-sm"
                                  disabled={ocupado}
                                  onClick={() => aprobar(p)}
                                >
                                  Aprobar
                                </button>
                                <button
                                  className="btn-danger btn-sm"
                                  onClick={() =>
                                    setMostrarRechazo(mostrarRechazo === p.id_pago ? null : p.id_pago)
                                  }
                                >
                                  Rechazar
                                </button>
                              </>
                            )}
                            {mostrarRechazo === p.id_pago && (
                              <div className="form-group" style={{ width: "100%", marginTop: "8px" }}>
                                <label>Motivo del rechazo</label>
                                <input
                                  value={motivoRechazo[p.id_pago] || ""}
                                  onChange={(e) =>
                                    setMotivoRechazo((m) => ({ ...m, [p.id_pago]: e.target.value }))
                                  }
                                />
                                <button
                                  className="btn-danger btn-sm"
                                  disabled={ocupado}
                                  onClick={() => rechazar(p)}
                                >
                                  Confirmar rechazo
                                </button>
                              </div>
                            )}
                            {esAdmin && (
                              <button
                                className="btn-secondary btn-sm"
                                onClick={() => {
                                  setAuditoriaPago(p);
                                  setAuditoriaMonto(String(p.monto ?? ""));
                                  setAuditoriaReferencia(p.referencia || "");
                                  setError("");
                                }}
                                title="Comparar el comprobante con el pago"
                              >
                                Auditar
                              </button>
                            )}
                            <button className="btn-secondary btn-sm" onClick={() => descargarRecibo(p)}>
                              Recibo
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {/* ================= CAJA ================= */}
      {pestana === "caja" && (
        <>
          <div className="panel" style={{ marginBottom: "20px" }}>
            <div className="panel-head">
              <h3>Mi turno de caja</h3>
              <span className="hint" style={{ margin: 0 }}>
                El efectivo solo se registra con el turno abierto
              </span>
            </div>
            {!turno?.id_turno ? (
              tieneEmpleado ? (
                <button className="btn-success" onClick={abrirTurno} disabled={ocupado}>
                  Abrir turno
                </button>
              ) : (
                <div className="hint">
                  Tu usuario no tiene ficha de empleado, asi que no puedes abrir un turno de
                  caja. Pide al administrador que te registre como empleado.
                </div>
              )
            ) : (
              <div>
                <p>
                  Turno #{turno.id_turno} · abierto {fechaCorta(turno.hora_apertura)}
                </p>
                {turno.estado === "cerrado" ? (
                  <span className="badge devuelto">Cerrado</span>
                ) : (
<button
                  className="btn-warning"
                  onClick={() => {
                    const esperado = Number(arqueo?.monto_esperado_efectivo ?? 0);
                    setCierreFisico(String(Number.isFinite(esperado) ? esperado : 0));
                    setCierreObservacion("");
                    setError("");
                    setMostrarCierre(true);
                  }}
                  disabled={ocupado}
                >
                  Cerrar y arquear
                </button>
                )}
              </div>
            )}
          </div>

          {arqueo && (
            <div className="grid mid" style={{ marginBottom: "20px" }}>
              <div className="panel">
                <h3>Efectivo esperado</h3>
                <div className="big-number">{bs(arqueo.monto_esperado_efectivo)}</div>
              </div>
              <div className="panel">
                <h3>Devoluciones en el turno</h3>
                <div className="big-number">{bs(arqueo.total_devuelto_efectivo)}</div>
                <div className="hint">{arqueo.cantidad_devoluciones} devolución(es)</div>
              </div>
              <div className="panel">
                <h3>Digital validado</h3>
                <div className="big-number">{bs(arqueo.total_digital)}</div>
              </div>
              <div className="panel">
                <h3>Pagos del turno</h3>
                <div className="big-number">{arqueo.cantidad_pagos}</div>
              </div>
            </div>
          )}

          {arqueo && arqueo.pagos && arqueo.pagos.length > 0 && (
            <div className="panel" style={{ marginBottom: "20px" }}>
              <div className="panel-head">
                <h3>Pagos del turno</h3>
              </div>
              <div className="tabla-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Reserva</th>
                      <th>Método</th>
                      <th>Monto</th>
                      <th>Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {arqueo.pagos.map((p) => (
                      <tr key={p.id_pago}>
                        <td>{p.id_pago}</td>
                        <td>#{p.id_reserva}</td>
                        <td className="capitalize">{p.metodo_pago}</td>
                        <td>{bs(p.monto)}</td>
                        <td>
                          <span className={`badge ${p.estado_pago}`}>{p.estado_label}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="panel">
            <div className="panel-head">
              <h3>Turnos registrados</h3>
            </div>
            {turnos.length === 0 ? (
              <div className="estado-vacio">Todavía no hay turnos de caja.</div>
            ) : (
              <div className="tabla-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Empleado</th>
                      <th>Fecha</th>
                      <th>Apertura</th>
                      <th>Cierre</th>
                      <th>Efectivo esperado</th>
                      <th>Diferencia</th>
                      <th>Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {turnos.map((t) => (
                      <tr key={t.id_turno}>
                        <td>{t.id_turno}</td>
                        <td>{t.empleado || `#${t.id_empleado}`}</td>
                        <td>{t.fecha}</td>
                        <td>{fechaCorta(t.hora_apertura)}</td>
                        <td>{fechaCorta(t.hora_cierre)}</td>
                        <td>{bs(t.monto_esperado_efectivo)}</td>
                        <td>
                          {t.diferencia === null || t.diferencia === undefined
                            ? "-"
                            : bs(t.diferencia)}
                        </td>
                        <td>
                          <span className={`badge ${t.estado === "abierto" ? "pendiente" : "aprobado"}`}>
                            {t.estado}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      {/* ================= DEVOLUCIONES ================= */}
      {pestana === "devoluciones" && (
        <div className="panel">
          <div className="panel-head">
            <h3>Solicitudes de devolución</h3>
            <span className="hint" style={{ margin: 0 }}>
              El pago pasa a devuelto cuando apruebas la solicitud
            </span>
          </div>
          {devoluciones.length === 0 ? (
            <div className="estado-vacio">No hay solicitudes de devolución.</div>
          ) : (
            <div className="tabla-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Pago</th>
                    <th>Monto</th>
                    <th>Motivo</th>
                    <th>Estado</th>
                    <th>Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {devoluciones.map((d) => (
                    <tr key={d.id_solicitud}>
                      <td>{d.id_solicitud}</td>
                      <td>
                        #{d.id_pago}
                        {d.pago?.reserva && (
                          <div className="hint">Reserva #{d.pago.reserva.id_reserva}</div>
                        )}
                      </td>
                      <td>{bs(d.monto)}</td>
                      <td>
                        {d.motivo}
                        {d.motivo_decision && <div className="hint">{d.motivo_decision}</div>}
                      </td>
                      <td>
                        <span
                          className={`badge ${
                            d.estado === "aprobada"
                              ? "aprobado"
                              : d.estado === "rechazada"
                                ? "rechazado"
                                : "pendiente_validacion"
                          }`}
                        >
                          {d.estado}
                        </span>
                      </td>
                      <td>
                        {d.estado === "solicitada" && esOperacion && (
                          <div style={{ display: "flex", gap: "6px" }}>
                            <button
                              className="btn-success btn-sm"
                              disabled={ocupado}
                              onClick={() => decidirDevolucion(d, "aprobar")}
                            >
                              Aprobar
                            </button>
                            <button
                              className="btn-danger btn-sm"
                              disabled={ocupado}
                              onClick={() => {
                                setDevolucionAbierta(d);
                                setDevolucionMotivo("");
                                setError("");
                              }}
                            >
                              Rechazar
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ================= AUDITORIA ================= */}
      {pestana === "auditoria" && esAdmin && (
        <div className="panel">
          <div className="panel-head">
            <h3>Auditoría de comprobantes</h3>
            <span className="hint" style={{ margin: 0 }}>
              Compara el comprobante recibido contra el pago registrado
            </span>
          </div>
          {auditorias.length === 0 ? (
            <div className="estado-vacio">Todavía no hay auditorías registradas.</div>
          ) : (
            <div className="tabla-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Pago</th>
                    <th>Resultado</th>
                    <th>Monto comprobante</th>
                    <th>Observaciones</th>
                    <th>Fecha</th>
                  </tr>
                </thead>
                <tbody>
                  {auditorias.map((a) => (
                    <tr key={a.id_auditoria}>
                      <td>{a.id_auditoria}</td>
                      <td>#{a.id_pago}</td>
                      <td>
                        <span className={`badge ${a.resultado === "conforme" ? "aprobado" : "rechazado"}`}>
                          {a.resultado}
                        </span>
                      </td>
                      <td>{a.monto_comprobante === null ? "-" : bs(a.monto_comprobante)}</td>
                      <td>{a.observaciones || "-"}</td>
                      <td>{fechaCorta(a.fecha)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ===== CIERRE DE CAJA =====
          Formulario en vez de window.prompt: el prompt no admite type/min, y
          un valor no numérico llegaba al backend como null (NaN serializado). */}
      <Modal
        isOpen={mostrarCierre}
        onClose={() => setMostrarCierre(false)}
        title="Cerrar turno y arquear"
      >
        <form onSubmit={confirmarCierre}>
          <div className="form-group">
            <label>Efectivo contado en caja (Bs)</label>
            <input
              type="number"
              step="0.01"
              min="0"
              max={MONTO_MAX}
              value={cierreFisico}
              onChange={(e) => setCierreFisico(e.target.value)}
              autoFocus
            />
            <small className="hint">
              Esperado según el sistema: {bs(arqueo?.monto_esperado_efectivo)}
            </small>
          </div>
          <div className="form-group">
            <label>Observaciones</label>
            <textarea
              value={cierreObservacion}
              onChange={(e) => setCierreObservacion(e.target.value)}
              maxLength={300}
              placeholder="Obligatoria si el monto no coincide con el esperado."
            />
          </div>
          <div className="modal-actions">
            <button type="submit" className="btn-warning" disabled={ocupado}>
              Cerrar turno
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => setMostrarCierre(false)}
            >
              Cancelar
            </button>
          </div>
        </form>
      </Modal>

      {/* ===== AUDITORÍA DE COMPROBANTE ===== */}
      <Modal
        isOpen={auditoriaPago !== null}
        onClose={() => setAuditoriaPago(null)}
        title={`Auditar comprobante del pago #${auditoriaPago?.id_pago ?? ""}`}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (auditoriaPago) auditar(auditoriaPago);
          }}
        >
          <div className="form-group">
            <label>Monto que indica el comprobante (Bs)</label>
            <input
              type="number"
              step="0.01"
              min="0.01"
              max={MONTO_MAX}
              value={auditoriaMonto}
              onChange={(e) => setAuditoriaMonto(e.target.value)}
              autoFocus
            />
            <small className="hint">Pago registrado: {bs(auditoriaPago?.monto)}</small>
          </div>
          <div className="form-group">
            <label>Referencia del comprobante</label>
            <input
              type="text"
              value={auditoriaReferencia}
              onChange={(e) => setAuditoriaReferencia(e.target.value)}
              maxLength={120}
            />
          </div>
          <div className="modal-actions">
            <button type="submit" className="btn-primary" disabled={ocupado}>
              Registrar auditoría
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => setAuditoriaPago(null)}
            >
              Cancelar
            </button>
          </div>
        </form>
      </Modal>

      {/* ===== RECHAZO DE DEVOLUCIÓN ===== */}
      <Modal
        isOpen={devolucionAbierta !== null}
        onClose={() => setDevolucionAbierta(null)}
        title="Rechazar devolución"
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (devolucionAbierta) decidirDevolucion(devolucionAbierta, "rechazar");
          }}
        >
          <div className="form-group">
            <label>Motivo del rechazo</label>
            <textarea
              value={devolucionMotivo}
              onChange={(e) => setDevolucionMotivo(e.target.value)}
              maxLength={300}
              required
              autoFocus
              placeholder="Por qué se rechaza la devolución."
            />
          </div>
          <div className="modal-actions">
            <button type="submit" className="btn-danger" disabled={ocupado}>
              Rechazar devolución
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => setDevolucionAbierta(null)}
            >
              Cancelar
            </button>
          </div>
        </form>
      </Modal>
    </AppLayout>
  );
};

export default PagosPage;
