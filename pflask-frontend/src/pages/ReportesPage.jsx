import { useEffect, useState } from "react";
import AppLayout from "../components/layout/AppLayout";
import { reportesService } from "../services/reportes";
import { api } from "../services/api";
import { esNumeroValido } from "../utils/validaciones";

const TIPOS = [
  { value: "reservas", label: "📋 Reservas por cancha" },
  { value: "ocupacion", label: "📈 Ocupación por cancha" },
  { value: "ingresos", label: "💰 Ingresos por cancha" },
];

const ReportesPage = () => {
  const [tipo, setTipo] = useState("reservas");
  const [fechaInicio, setFechaInicio] = useState("");
  const [fechaFin, setFechaFin] = useState("");
  const [cancha, setCancha] = useState("");
  const [cliente, setCliente] = useState("");
  const [estado, setEstado] = useState("");
  const [canchas, setCanchas] = useState([]);
  const [estados, setEstados] = useState([]);
  const [filas, setFilas] = useState([]);
  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);
  const [generado, setGenerado] = useState(false);

  useEffect(() => {
    reportesService.catalogos().then((d) => setEstados(d.estados)).catch(() => {});
    api.get("/canchas").then((d) => setCanchas(d.data || [])).catch(() => {});
  }, []);

  const filtros = () => {
    const f = {};
    if (cancha) f.id_cancha = Number(cancha);
    if (cliente) f.id_cliente = Number(cliente);
    if (estado) f.estado = estado;
    return f;
  };

  const generar = async () => {
    setError("");
    setFilas([]);
    setMensaje("");
    setGenerado(false);

    if (!fechaInicio || !fechaFin) {
      setError("Debe indicar fecha inicio y fecha fin.");
      return;
    }
    if (fechaInicio > fechaFin) {
      setError("La fecha de inicio no puede ser mayor que la fecha fin.");
      return;
    }
    // id_cliente queda como texto en el input: sin convertirlo el backend
    // recibe una cadena y la consulta por cliente no filtra nada.
    if (cliente && !esNumeroValido(cliente, { entero: true, min: 1 })) {
      setError("El ID del cliente debe ser un número entero válido.");
      return;
    }

    setCargando(true);
    try {
      const data = await reportesService.obtener(tipo, fechaInicio, fechaFin, filtros());
      setFilas(data.filas || []);
      setMensaje(data.mensaje || "");
      setGenerado(true);
    } catch (e) {
      setError(e.response?.data?.error || "No se pudo generar el reporte.");
    } finally {
      setCargando(false);
    }
  };

  const exportar = async (formato) => {
    setError("");
    try {
      await reportesService.descargar(tipo, fechaInicio, fechaFin, formato, filtros());
    } catch (e) {
      setError(e.response?.data?.error || "No se pudo exportar el reporte.");
    }
  };

  const limpiar = () => {
    setCancha("");
    setCliente("");
    setEstado("");
  };

  const encabezados = filas.length > 0 ? Object.keys(filas[0]) : [];
  const hayFiltros = !!(cancha || cliente || estado);

  return (
    <AppLayout title="Gestión de Reportes" subtitle="Reportes, ocupación e ingresos con exportación">
      <div className="grid mid">
        <div className="panel">
          <div className="panel-head">
            <h3>Filtros del reporte</h3>
            {hayFiltros && (
              <button className="btn-secondary btn-sm" onClick={limpiar}>
                Limpiar filtros
              </button>
            )}
          </div>

          <div className="form-group">
            <label>Tipo de informe</label>
            <select value={tipo} onChange={(e) => setTipo(e.target.value)}>
              {TIPOS.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>

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

          <div className="form-row">
            <div className="form-group">
              <label>Cancha</label>
              <select value={cancha} onChange={(e) => setCancha(e.target.value)}>
                <option value="">Todas</option>
                {canchas.map((c) => (
                  <option key={c.id_cancha} value={c.id_cancha}>
                    {c.nombre_cancha}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label>ID de cliente</label>
              <input
                type="number"
                min="1"
                step="1"
                value={cliente}
                onChange={(e) => setCliente(e.target.value)}
                placeholder="Todos"
              />
            </div>
          </div>

          <div className="form-group">
            <label>Estado de la reserva</label>
            <select value={estado} onChange={(e) => setEstado(e.target.value)}>
              <option value="">Todos</option>
              {estados.map((s) => (
                <option key={s.valor} value={s.valor}>
                  {s.etiqueta}
                </option>
              ))}
            </select>
          </div>

          <button
            className="btn-primary"
            onClick={generar}
            disabled={cargando}
            style={{ width: "100%" }}
          >
            {cargando ? "Generando..." : "🔍 Generar reporte"}
          </button>

          {error && <div className="mensaje error">{error}</div>}
        </div>

        <div className="panel">
          <div className="panel-head">
            <h3>Información</h3>
            <span className="hint" style={{ margin: 0 }}>Disponible para administradores</span>
          </div>
          <ul style={{ paddingLeft: "20px", margin: 0, fontSize: "14px", lineHeight: 1.8 }}>
            <li><b>Reservas por cancha:</b> total, reservadas, confirmadas, finalizadas, canceladas y expiradas.</li>
            <li><b>Ocupación por cancha:</b> solo cuenta las reservas confirmadas y finalizadas, dividido entre las horas reales de cada cancha.</li>
            <li><b>Ingresos por cancha:</b> pagos aprobados menos devoluciones. No es la suma de las reservas.</li>
            <li>Los tres reportes miden el rango por la <b>fecha de la reserva</b>, para que sean comparables.</li>
            <li>Exporta el resultado en <b>PDF</b> o <b>Excel</b>. Cada generación queda registrada.</li>
          </ul>
        </div>
      </div>

      {generado && mensaje === "sin datos" && (
        <div className="estado-vacio">📭 sin datos</div>
      )}

      {filas.length > 0 && (
        <div className="panel" style={{ marginTop: "20px" }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "10px",
              marginBottom: "12px",
            }}
          >
            <div>
              <h3 style={{ margin: 0 }}>
                Resultado ({filas.length} registro{filas.length === 1 ? "" : "s"})
              </h3>
              <span className="hint">
                {fechaInicio} a {fechaFin}
                {hayFiltros ? ` · ${mensaje}` : ""}
              </span>
            </div>
            <div className="acciones">
              <button
                className="btn-danger btn-sm"
                onClick={() => exportar("pdf")}
                style={{ textDecoration: "none" }}
              >
                📄 Exportar PDF
              </button>
              <button
                className="btn-success btn-sm"
                onClick={() => exportar("excel")}
                style={{ textDecoration: "none" }}
              >
                📊 Exportar Excel
              </button>
            </div>
          </div>

          <div className="tabla-wrapper">
            <table>
              <thead>
                <tr>
                  {encabezados.map((k) => (
                    <th key={k}>{k.replace(/_/g, " ")}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filas.map((fila, i) => (
                  <tr key={i}>
                    {Object.values(fila).map((v, j) => (
                      <td key={j}>{String(v)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </AppLayout>
  );
};

export default ReportesPage;
