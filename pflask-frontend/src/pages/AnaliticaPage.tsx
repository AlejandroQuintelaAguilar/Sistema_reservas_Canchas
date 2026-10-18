import { useEffect, useMemo, useState } from "react";
import AppLayout from "../components/layout/AppLayout";
import { api } from "../services/api";
import { analiticaService } from "../services/analitica";
import type {
  Analisis,
  ResumenAnalisis,
  TipoAnalisis,
  TipoCatalogo,
  ParametroAnalisis,
} from "../services/analitica";
import { aNumero, esNumeroValido } from "../utils/validaciones";

/** Etiquetas legibles de cada metrica, para no pintar claves crudas. */
const METRICAS: Record<string, string> = {
  total_reservas: "Total de reservas",
  reservas_cobradas: "Reservas confirmadas/finalizadas",
  tasa_cancelacion: "Tasa de cancelacion (%)",
  tasa_expiracion: "Tasa de expiracion (%)",
  duracion_promedio_horas: "Duracion promedio (horas)",
  horario_mayor_demanda: "Horario de mayor demanda",
  reservas_por_cliente_promedio: "Reservas por cliente (promedio)",
  total_pagos: "Total de pagos",
  ingresos_brutos: "Ingresos brutos",
  ingresos_netos: "Ingresos netos",
  devoluciones: "Devoluciones",
  monto_promedio: "Monto promedio",
  metodo_mayor_ingreso: "Metodo de mayor ingreso",
  dias_con_pagos: "Dias con pagos",
  tasa_expiracion_pago: "Tasa de expiracion de pagos (%)",
  total_canchas: "Total de canchas",
  canchas_con_ocupacion: "Canchas con ocupacion",
  canchas_sin_ocupacion: "Canchas sin ocupacion",
  ocupacion_promedio: "Ocupacion promedio (%)",
  horas_disponibles: "Horas disponibles",
  horas_reservadas: "Horas reservadas",
  ingresos: "Ingresos",
  total_clientes: "Total de clientes",
  clientes_con_reservas: "Clientes con reservas",
  clientes_sin_reservas: "Clientes sin reservas",
  total_gastado: "Total gastado",
  concentracion_top5: "Concentracion top 5 (%)",
  tasa_cancelacion_clientes: "Tasa de cancelacion (%)",
  tasa_expiracion_clientes: "Tasa de expiracion (%)",
  tasa_rechazo: "Tasa de rechazo de pagos (%)",
  ticket_promedio: "Ticket promedio",
  cliente_mas_frecuente: "Cliente mas frecuente",
  cliente_mayor_gasto: "Cliente de mayor gasto",
  cancha_mayor_ocupacion: "Cancha de mayor ocupacion",
  cancha_mayor_ingreso: "Cancha de mayor ingreso",
  mas_ociosas: "Canchas mas ociosas",
  total_por_cobrar: "Total por cobrar",
  clientes_con_saldo: "Clientes con saldo pendiente",
  dias_con_reservas: "Dias con reservas",
};

/** Metricas que son montos en bolivianos y no numeros simples. */
const DINERO = new Set([
  "ingresos_brutos",
  "ingresos_netos",
  "devoluciones",
  "total_gastado",
  "ingresos",
  "total_por_cobrar",
  "ticket_promedio",
  "monto_promedio",
]);

const ETIQUETA_TIPO: Record<string, string> = {
  reservas: "Reservas",
  pagos: "Pagos",
  canchas: "Canchas",
  clientes: "Clientes",
};

/** Titulo de cada tabla del detalle, en el orden en que llega del backend. */
const TITULO_TABLA: Record<string, string> = {
  por_estado: "Reservas por estado",
  por_canal: "Reservas por canal de origen",
  por_horario: "Reservas por hora del dia",
  por_dia_semana: "Reservas por dia de la semana",
  por_cancha: "Reservas por cancha",
  por_metodo: "Pagos por metodo",
  por_dia: "Pagos por dia",
  detalle_canchas: "Detalle por cancha",
  detalle_clientes: "Detalle por cliente",
};

/** Secciones que no son tablas de filas. */
const SECCIONES_ESPECIALES = new Set(["avisos", "resumen", "notas", "sin_datos"]);

const hoy = () => new Date().toISOString().slice(0, 10);
const hace30 = () => {
  const d = new Date();
  d.setDate(d.getDate() - 30);
  return d.toISOString().slice(0, 10);
};

const nf = new Intl.NumberFormat("es-BO", { maximumFractionDigits: 2 });
const fmtNum = (v: unknown) => (typeof v === "number" ? nf.format(v) : String(v ?? "-"));
const fmtBs = (v: unknown) => (typeof v === "number" ? `Bs ${nf.format(v)}` : String(v ?? "-"));

const valor = (clave: string, v: unknown) => (DINERO.has(clave) ? fmtBs(v) : fmtNum(v));

/** Normaliza el detalle del backend en una lista de tablas con titulo. */
interface Tabla {
  titulo: string;
  clave: string;
  filas: Record<string, unknown>[];
}

const tablasDe = (resultado: unknown): Tabla[] => {
  if (!resultado || typeof resultado !== "object") return [];
  return Object.entries(resultado as Record<string, unknown>)
    .filter(([clave]) => !SECCIONES_ESPECIALES.has(clave))
    .map(([clave, v]) => {
      let filas: Record<string, unknown>[];
      if (Array.isArray(v)) {
        filas = v.filter((f) => f && typeof f === "object" && !Array.isArray(f)) as Record<
          string,
          unknown
        >[];
      } else if (v && typeof v === "object") {
        filas = [v as Record<string, unknown>];
      } else {
        filas = [];
      }
      return { titulo: TITULO_TABLA[clave] || clave.replace(/_/g, " "), clave, filas };
    })
    .filter((t) => t.filas.length > 0);
};

/** Texto legible de un error de axios. */
const errMsg = (e: unknown, porDefecto: string) => {
  const r = e as { response?: { data?: { error?: string } } };
  return r?.response?.data?.error || porDefecto;
};

const AnaliticaPage = () => {
  const [tipos, setTipos] = useState<TipoCatalogo[]>([]);
  const [canchas, setCanchas] = useState<{ id_cancha: number; nombre_cancha: string }[]>([]);
  const [tipo, setTipo] = useState<TipoAnalisis>("reservas");
  const [fechaInicio, setFechaInicio] = useState(hace30);
  const [fechaFin, setFechaFin] = useState(hoy);
  const [params, setParams] = useState<Record<string, unknown>>({});

  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);
  const [sinDatos, setSinDatos] = useState(false);
  const [ultimoId, setUltimoId] = useState<number | null>(null);

  const [historial, setHistorial] = useState<ResumenAnalisis[]>([]);
  const [filtroTipo, setFiltroTipo] = useState("");
  const [filtroDesde, setFiltroDesde] = useState("");
  const [filtroHasta, setFiltroHasta] = useState("");
  const [detalle, setDetalle] = useState<Analisis | null>(null);
  const [vistos, setVistos] = useState<number[]>([]);

  const [compararFila, setCompararFila] = useState<ResumenAnalisis | null>(null);
  const [cFechaInicio, setCFechaInicio] = useState(hace30);
  const [cFechaFin, setCFechaFin] = useState(hoy);
  const [cmp, setCmp] = useState<{
    diferencias: Record<string, number | null>;
    actual: Record<string, unknown>;
    mensaje: string;
  } | null>(null);

  const catalogo = useMemo(() => tipos.find((t) => t.valor === tipo), [tipos, tipo]);

  useEffect(() => {
    analiticaService
      .catalogos()
      .then((d) => setTipos(d.tipos || []))
      .catch(() => {});
    api
      .get("/canchas")
      .then((d) => setCanchas(d.data || []))
      .catch(() => {});
  }, []);

  const cargarHistorial = async () => {
    try {
      const data = await analiticaService.listar({
        tipo_analisis: filtroTipo || undefined,
        desde: filtroDesde || undefined,
        hasta: filtroHasta || undefined,
        limite: 50,
      });
      setHistorial(data);
      setVistos((v) => Array.from(new Set([...v, ...data.map((x) => x.id_analisis)])));
    } catch (e) {
      setError(errMsg(e, "No se pudo cargar el historial."));
    }
  };

  useEffect(() => {
    cargarHistorial();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtroTipo, filtroDesde, filtroHasta]);

  const limpiarFormulario = (tipoActual: string) => {
    setTipo(tipoActual as TipoAnalisis);
    setParams({});
    setDetalle(null);
    setSinDatos(false);
    setUltimoId(null);
  };

  const setParam = (nombre: string, v: unknown) => {
    setParams((p) => {
      const copia = { ...p };
      if (v === "" || v === false || v === undefined) delete copia[nombre];
      else copia[nombre] = v;
      return copia;
    });
  };

  const generar = async () => {
    setError("");
    setDetalle(null);
    setSinDatos(false);
    setUltimoId(null);

    if (!fechaInicio || !fechaFin) {
      setError("Debe indicar fecha de inicio y fecha de fin.");
      return;
    }
    if (fechaInicio > fechaFin) {
      setError("La fecha de inicio no puede ser posterior a la fecha de fin.");
      return;
    }
    // Los parámetros numéricos llegan como texto desde el input; sin convertirlos
    // el backend los recibe como string y el análisis falla al agregar.
    const parametros: Record<string, unknown> = { ...params };
    for (const [clave, valor] of Object.entries(params)) {
      const def = tipos
        .flatMap((t) => t.parametros ?? [])
        .find((x) => x.nombre === clave);
      if (def?.tipo === "numero") {
        const n = aNumero(valor);
        if (!esNumeroValido(n, { entero: true })) {
          setError(`"${def.etiqueta}" debe ser un número entero válido.`);
          return;
        }
        parametros[clave] = n;
      } else if (def?.tipo === "fecha" && !/^\d{4}-\d{2}-\d{2}$/.test(String(valor))) {
        setError(`"${def.etiqueta}" debe tener el formato AAAA-MM-DD.`);
        return;
      }
    }

    setCargando(true);
    try {
      const r = await analiticaService.generar({
        tipo_analisis: tipo,
        fecha_inicio: fechaInicio,
        fecha_fin: fechaFin,
        parametros,
      });
      setSinDatos(r.mensaje === "sin datos");
      setDetalle(r.analisis);
      setUltimoId(r.analisis?.id_analisis ?? null);
      await cargarHistorial();
    } catch (e) {
      setError(errMsg(e, "No se pudo generar el analisis."));
    } finally {
      setCargando(false);
    }
  };

  const verDetalle = async (id: number) => {
    setError("");
    setSinDatos(false);
    setUltimoId(id);
    try {
      setDetalle(await analiticaService.detalle(id));
    } catch (e) {
      setDetalle(null);
      setError(errMsg(e, "No se pudo abrir el analisis."));
    }
  };

  const eliminar = async (id: number) => {
    if (!window.confirm("Eliminar este analisis del historial? No se puede deshacer.")) return;
    setError("");
    try {
      await analiticaService.eliminar(id);
      if (detalle?.id_analisis === id) setDetalle(null);
      if (ultimoId === id) setUltimoId(null);
      if (compararFila?.id_analisis === id) {
        setCompararFila(null);
        setCmp(null);
      }
      await cargarHistorial();
    } catch (e) {
      setError(errMsg(e, "No se pudo eliminar el analisis."));
    }
  };

  const exportar = async (id: number, formato: "pdf" | "excel") => {
    setError("");
    try {
      await analiticaService.descargar(id, formato);
    } catch (e) {
      setError(errMsg(e, "No se pudo exportar el analisis."));
    }
  };

  const comparar = async () => {
    if (!compararFila) return;
    setError("");
    if (cFechaInicio > cFechaFin) {
      setError("En la comparacion la fecha de inicio no puede ser posterior a la de fin.");
      return;
    }
    setCargando(true);
    try {
      const r = await analiticaService.comparar(
        compararFila.id_analisis,
        cFechaInicio,
        cFechaFin
      );
      setCmp({
        diferencias: r.diferencias || {},
        actual: (r.actual?.metricas as Record<string, unknown>) || {},
        mensaje: r.mensaje || "",
      });
    } catch (e) {
      setError(errMsg(e, "No se pudo comparar."));
    } finally {
      setCargando(false);
    }
  };

  const parametro = (p: ParametroAnalisis) => {
    const v = params[p.nombre];

    if (p.tipo === "booleano") {
      return (
        <div className="form-group" key={p.nombre}>
          <div className="acciones">
            <label style={{ display: "flex", gap: "8px", alignItems: "center" }}>
              <input
                type="checkbox"
                checked={!!v}
                onChange={(e) => setParam(p.nombre, e.target.checked)}
              />
              {p.etiqueta}
            </label>
          </div>
        </div>
      );
    }

    if (p.tipo === "lista" && p.opciones?.length) {
      const lista = (v as string[]) || [];
      return (
        <div className="form-group" key={p.nombre}>
          <label>
            {p.etiqueta}
            {lista.length > 0 ? ` (${lista.length} marcados)` : ""}
          </label>
          <div className="acciones">
            {p.opciones.map((o) => {
              const activo = lista.includes(o.valor);
              return (
                <button
                  type="button"
                  key={o.valor}
                  className={`btn-secondary btn-sm ${activo ? "" : ""}`}
                  style={
                    activo
                      ? { background: "var(--color-info)", color: "#fff", borderColor: "transparent" }
                      : undefined
                  }
                  onClick={() =>
                    setParam(
                      p.nombre,
                      activo ? lista.filter((x) => x !== o.valor) : [...lista, o.valor]
                    )
                  }
                >
                  {activo ? "✓ " : ""}
                  {o.etiqueta}
                </button>
              );
            })}
          </div>
        </div>
      );
    }

    if (p.nombre === "id_cancha") {
      return (
        <div className="form-group" key={p.nombre}>
          <label>{p.etiqueta}</label>
          <select value={String(v ?? "")} onChange={(e) => setParam(p.nombre, e.target.value)}>
            <option value="">Todas</option>
            {canchas.map((c) => (
              <option key={c.id_cancha} value={c.id_cancha}>
                {c.nombre_cancha}
              </option>
            ))}
          </select>
        </div>
      );
    }

    return (
      <div className="form-group" key={p.nombre}>
        <label>{p.etiqueta}</label>
        <input
          type={p.tipo === "numero" || p.tipo === "fecha" ? p.tipo : "text"}
          value={String(v ?? "")}
          onChange={(e) => setParam(p.nombre, e.target.value)}
          {...(p.tipo === "numero" ? { step: "1", min: 0 } : {})}
        />
      </div>
    );
  };

  const metricas = (detalle?.metricas || {}) as Record<string, unknown>;
  const tablas = tablasDe(detalle?.resultado);
  const corruptos = historial.filter((a) => a.estado === "corrupto").length;

  return (
    <AppLayout
      title="Analitica de Datos"
      subtitle="Genera analisis por rango de fechas, guardalos y comparalos"
    >
      <div className="grid mid">
        <div className="panel">
          <div className="panel-head">
            <h3>Nuevo analisis</h3>
            <span className="hint" style={{ margin: 0 }}>
              Solo administradores
            </span>
          </div>

          <div className="form-group">
            <label>Tipo de analisis</label>
            <select value={tipo} onChange={(e) => limpiarFormulario(e.target.value)}>
              {tipos.map((t) => (
                <option key={t.valor} value={t.valor}>
                  {t.etiqueta}
                </option>
              ))}
            </select>
          </div>
          {catalogo?.descripcion && (
            <p className="hint" style={{ marginTop: "-6px" }}>
              {catalogo.descripcion}
            </p>
          )}

          <div className="form-row">
            <div className="form-group">
              <label>Fecha inicio</label>
              <input type="date" value={fechaInicio} max={fechaFin} onChange={(e) => setFechaInicio(e.target.value)} />
            </div>
            <div className="form-group">
              <label>Fecha fin</label>
              <input type="date" value={fechaFin} min={fechaInicio} onChange={(e) => setFechaFin(e.target.value)} />
            </div>
          </div>

          {catalogo?.parametros?.map(parametro)}

          <div className="acciones" style={{ marginTop: "8px" }}>
            <button className="btn-primary" onClick={generar} disabled={cargando} style={{ flex: 1 }}>
              {cargando ? "Generando..." : "Generar analisis"}
            </button>
            <button
              className="btn-secondary"
              onClick={() => limpiarFormulario(tipo)}
              disabled={cargando}
              title="Quitar filtros"
            >
              Limpiar
            </button>
          </div>

          {error && <div className="mensaje error">{error}</div>}
        </div>

        <div className="panel">
          <div className="panel-head">
            <h3>Historial de analisis</h3>
            <button className="btn-secondary btn-sm" onClick={cargarHistorial}>
              Actualizar
            </button>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Tipo</label>
              <select value={filtroTipo} onChange={(e) => setFiltroTipo(e.target.value)}>
                <option value="">Todos</option>
                {tipos.map((t) => (
                  <option key={t.valor} value={t.valor}>
                    {t.etiqueta}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label>Desde</label>
              <input
              type="date"
              value={filtroDesde}
              max={filtroHasta || undefined}
              onChange={(e) => setFiltroDesde(e.target.value)}
            />
            </div>
            <div className="form-group">
              <label>Hasta</label>
              <input
              type="date"
              value={filtroHasta}
              min={filtroDesde || undefined}
              onChange={(e) => setFiltroHasta(e.target.value)}
            />
            </div>
          </div>

          {corruptos > 0 && (
            <div className="mensaje info">
              {corruptos} registro(s) del historial estan danados. Se muestran marcados como
              "corrupto" y puedes eliminarlos para volver a generarlos.
            </div>
          )}

          {historial.length === 0 ? (
            <p className="hint">Todavia no hay analisis guardados.</p>
          ) : (
            <div className="tabla-wrapper" style={{ maxHeight: "440px", overflowY: "auto" }}>
              <table>
                <thead>
                  <tr>
                    <th>Analisis</th>
                    <th>Rango</th>
                    <th>Generado</th>
                    <th>Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {historial.map((a) => (
                    <tr
                      key={a.id_analisis}
                      style={
                        ultimoId === a.id_analisis
                          ? { outline: "1px solid var(--color-info)" }
                          : undefined
                      }
                    >
                      <td>
                        <b>#{a.id_analisis}</b> {ETIQUETA_TIPO[a.tipo_analisis] || a.tipo_analisis}
                        <div className="hint">
                          {a.total_registros} registro(s)
                          {vistos.includes(a.id_analisis) && " · visto"}
                        </div>
                        {a.estado === "corrupto" ? (
                          <span className="badge fuera_servio" title={a.error}>
                            corrupto
                          </span>
                        ) : (
                          <span className="badge disponible">ok</span>
                        )}
                      </td>
                      <td>
                        {a.fecha_inicio}
                        <br />
                        {a.fecha_fin}
                      </td>
                      <td>
                        {a.generado_en?.slice(0, 16).replace("T", " ")}
                        {a.generado_por && <div className="hint">{a.generado_por}</div>}
                      </td>
                      <td className="acciones">
                        <button
                          className="btn-secondary btn-sm"
                          onClick={() => verDetalle(a.id_analisis)}
                        >
                          Ver
                        </button>
                        <button
                          className="btn-secondary btn-sm"
                          onClick={() => {
                            setCompararFila(a);
                            setCFechaInicio(a.fecha_inicio);
                            setCFechaFin(a.fecha_fin);
                            setCmp(null);
                          }}
                        >
                          Comparar
                        </button>
                        <button
                          className="btn-secondary btn-sm"
                          onClick={() => exportar(a.id_analisis, "excel")}
                        >
                          Excel
                        </button>
                        <button
                          className="btn-secondary btn-sm"
                          onClick={() => exportar(a.id_analisis, "pdf")}
                        >
                          PDF
                        </button>
                        <button
                          className="btn-danger btn-sm"
                          onClick={() => eliminar(a.id_analisis)}
                        >
                          Eliminar
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {sinDatos && (
        <div className="estado-vacio">
          sin datos
          <div className="hint">
            El rango no tiene registros, asi que no se guardo ningun analisis.
          </div>
        </div>
      )}

      {ultimoId && detalle && !sinDatos && (
        <div className="mensaje success" style={{ marginTop: "16px" }}>
          Analisis #{detalle.id_analisis} generado y guardado en el historial.
        </div>
      )}

      {compararFila && (
        <div className="panel" style={{ marginTop: "20px" }}>
          <div className="panel-head">
            <h3>
              Comparar #{compararFila.id_analisis} (
              {ETIQUETA_TIPO[compararFila.tipo_analisis] || compararFila.tipo_analisis}) con otro
              rango
            </h3>
            <button
              className="btn-secondary btn-sm"
              onClick={() => {
                setCompararFila(null);
                setCmp(null);
              }}
            >
              Cerrar
            </button>
          </div>
          <p className="hint">
            Se reaplican los filtros del analisis #{compararFila.id_analisis}. El rango nuevo se
            calcula pero <b>no se guarda</b>.
          </p>
          <div className="form-row">
            <div className="form-group">
              <label>Nuevo desde</label>
              <input
              type="date"
              value={cFechaInicio}
              max={cFechaFin}
              onChange={(e) => setCFechaInicio(e.target.value)}
            />
            </div>
            <div className="form-group">
              <label>Nuevo hasta</label>
              <input
              type="date"
              value={cFechaFin}
              min={cFechaInicio}
              onChange={(e) => setCFechaFin(e.target.value)}
            />
            </div>
            <div className="form-group">
              <label>&nbsp;</label>
              <button className="btn-primary" onClick={comparar} disabled={cargando}>
                {cargando ? "Comparando..." : "Comparar"}
              </button>
            </div>
          </div>

          {cmp?.mensaje && <div className="estado-vacio">{cmp.mensaje}</div>}

          {cmp && Object.keys(cmp.diferencias).length > 0 && (
            <div className="tabla-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>Metrica</th>
                    <th>Analisis #{compararFila.id_analisis}</th>
                    <th>Rango nuevo</th>
                    <th>Diferencia</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(cmp.diferencias).map(([clave, dif]) => {
                    const antes = (compararFila.metricas || {})[clave];
                    const despues = cmp.actual[clave];
                    return (
                      <tr key={clave}>
                        <td>{METRICAS[clave] || clave.replace(/_/g, " ")}</td>
                        <td>{valor(clave, antes)}</td>
                        <td>{valor(clave, despues)}</td>
                        <td>
                          {dif === null ? (
                            "-"
                          ) : (
                            <b
                              style={{
                                color:
                                  dif > 0
                                    ? "var(--color-disponible)"
                                    : dif < 0
                                      ? "var(--color-danger)"
                                      : "inherit",
                              }}
                            >
                              {dif > 0 ? "+" : ""}
                              {valor(clave, dif)}
                            </b>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {detalle && (
        <div className="panel" style={{ marginTop: "20px" }}>
          <div className="panel-head">
            <h3>
              Analisis #{detalle.id_analisis} -{" "}
              {ETIQUETA_TIPO[detalle.tipo_analisis] || detalle.tipo_analisis}
            </h3>
            <div className="acciones">
              <button
                className="btn-secondary btn-sm"
                onClick={() => exportar(detalle.id_analisis, "excel")}
              >
                Excel
              </button>
              <button
                className="btn-secondary btn-sm"
                onClick={() => exportar(detalle.id_analisis, "pdf")}
              >
                PDF
              </button>
            </div>
          </div>
          <p className="hint">
            Rango {detalle.fecha_inicio} a {detalle.fecha_fin} · generado{" "}
            {detalle.generado_en?.slice(0, 16).replace("T", " ")}
            {detalle.generado_por ? ` por ${detalle.generado_por}` : ""}
            {detalle.parametros && Object.keys(detalle.parametros).length > 0
              ? ` · filtros ${JSON.stringify(detalle.parametros)}`
              : " · sin filtros"}
          </p>

          {detalle.estado === "corrupto" ? (
            <div className="mensaje error">
              El registro guardado esta danado y no se pudo interpretar: {detalle.error}. Eliminalo
              y vuelve a generar el analisis.
            </div>
          ) : (
            <>
              {Object.entries(metricas).length > 0 && (
                <>
                  <h4 style={{ marginTop: "18px" }}>Metricas</h4>
                  <div className="grid stats">
                    {Object.entries(metricas).map(([clave, v]) => (
                      <div className="stat-card" key={clave}>
                        <div className="stat-top">
                          <span>{METRICAS[clave] || clave.replace(/_/g, " ")}</span>
                        </div>
                        <div className="stat-num">{valor(clave, v)}</div>
                      </div>
                    ))}
                  </div>
                </>
              )}

              {tablas.map((t) => (
                <div key={t.clave} style={{ marginTop: "20px" }}>
                  <h4>{t.titulo}</h4>
                  <div className="tabla-wrapper">
                    <table>
                      <thead>
                        <tr>
                          {Object.keys(t.filas[0]).map((k) => (
                            <th key={k}>{k.replace(/_/g, " ")}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {t.filas.map((fila, i) => (
                          <tr key={i}>
                            {Object.entries(fila).map(([k, v], j) => (
                              <td key={j}>{k.includes("monto") || k.includes("ingreso") || k.includes("total") ? valor(k, v) : fmtNum(v)}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </>
          )}
        </div>
      )}

      <div className="panel" style={{ marginTop: "20px" }}>
        <div className="panel-head">
          <h3>Como se calcula</h3>
        </div>
        <ul style={{ paddingLeft: "20px", margin: 0, fontSize: "14px", lineHeight: 1.8 }}>
          <li>
            <b>Reservas:</b> totales por estado, porcentaje de cancelacion y expiracion, duracion
            promedio y horario de mayor demanda. Solo cuentan como cobradas las confirmadas y las
            finalizadas.
          </li>
          <li>
            <b>Pagos:</b> ingresos brutos, devoluciones e <b>ingresos netos = brutos −
            devoluciones</b>. Pagos rechazados o expirados no suman ingreso.
          </li>
          <li>
            <b>Canchas:</b> ocupacion sobre las horas realmente disponibles de cada cancha, horas
            reservadas e ingresos atribuidos.
          </li>
          <li>
            <b>Clientes:</b> frecuencia de reservas, gasto total y que porcentaje del gasto
            concentra el top 5.
          </li>
          <li>Un rango sin datos no se guarda: se avisa <b>sin datos</b> y no queda registro.</li>
          <li>Comparar dos rangos no guarda el rango nuevo, solo muestra la diferencia.</li>
          <li>
            Este modulo es distinto de <b>Reportes</b>: aqui los analisis quedan guardados con sus
            parametros y metricas para poder consultarlos y compararlos mas tarde.
          </li>
        </ul>
      </div>
    </AppLayout>
  );
};

export default AnaliticaPage;
