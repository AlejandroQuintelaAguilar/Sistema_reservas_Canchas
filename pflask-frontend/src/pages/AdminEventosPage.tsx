import React, { useState, useMemo } from "react";
import {
  obtenerEstadoTemporalEvento,
  type Evento,
  type CreateEventoDTO,
} from "../types/evento.types";
import { TablaEventosAdmin } from "../components/admin/TablaEventosAdmin";
import { EventoFormModal } from "../components/admin/EventoFormModal";
import { useEventos } from "../hooks/useEventos";
import { AppLayout } from "../components/layout/AppLayout";

interface AdminEventosPageProps {
  eventos?: Evento[];
  loading?: boolean;
  error?: string | null;
  onCrearEvento?: (data: CreateEventoDTO) => Promise<void>;
  onActualizarEvento?: (id: number, data: CreateEventoDTO) => Promise<void>;
  onEliminarEvento?: (id: number) => Promise<void>;
}

type FiltroVigencia = "vigentes" | "pasados" | "todos";

export const AdminEventosPage: React.FC<AdminEventosPageProps> = (props) => {
  const hookData = useEventos();

  const eventos = props.eventos ?? hookData.eventos;
  const loading = props.loading ?? hookData.loading;
  const error = props.error ?? hookData.error;

  const onCrearEvento = props.onCrearEvento ?? hookData.crearEvento;
  const onActualizarEvento =
    props.onActualizarEvento ?? hookData.actualizarEvento;
  const onEliminarEvento = props.onEliminarEvento ?? hookData.eliminarEvento;

  const [modalAbierto, setModalAbierto] = useState(false);
  const [eventoEditar, setEventoEditar] = useState<Evento | null>(null);

  // Pestaña activa de vigencia: por defecto muestra los eventos próximos / en curso
  const [filtroVigencia, setFiltroVigencia] =
    useState<FiltroVigencia>("vigentes");

  // Filtros de búsqueda rápida para Administrador y Empleado
  const [busqueda, setBusqueda] = useState("");
  const [filtroTipo, setFiltroTipo] = useState("todos");
  const [filtroFecha, setFiltroFecha] = useState("");

  const contadoresVigencia = useMemo(() => {
    let vigentes = 0;
    let pasados = 0;
    for (const ev of eventos) {
      const est = obtenerEstadoTemporalEvento(ev);
      if (est === "pasado") {
        pasados++;
      } else {
        vigentes++;
      }
    }
    return {
      vigentes,
      pasados,
      todos: eventos.length,
    };
  }, [eventos]);

  const tiposDisponibles = useMemo(() => {
    return Array.from(
      new Set(eventos.map((e) => e.tipo_evento).filter(Boolean))
    ) as string[];
  }, [eventos]);

  const eventosFiltrados = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    const lista = eventos.filter((ev) => {
      const estadoTemp = obtenerEstadoTemporalEvento(ev);
      const coincideVigencia =
        filtroVigencia === "todos"
          ? true
          : filtroVigencia === "vigentes"
            ? estadoTemp !== "pasado"
            : estadoTemp === "pasado";

      const nombresCanchasTexto = (
        ev.nombres_canchas && ev.nombres_canchas.length > 0
          ? ev.nombres_canchas.join(" ")
          : ev.nombre_cancha || ""
      ).toLowerCase();

      const coincideTexto =
        !q ||
        ev.nombre_evento.toLowerCase().includes(q) ||
        nombresCanchasTexto.includes(q) ||
        (ev.organizador || "").toLowerCase().includes(q) ||
        (ev.contacto || "").toLowerCase().includes(q);
      const coincideTipo =
        filtroTipo === "todos" || ev.tipo_evento === filtroTipo;
      const coincideFecha = !filtroFecha || ev.fecha_evento === filtroFecha;

      return (
        coincideVigencia && coincideTexto && coincideTipo && coincideFecha
      );
    });

    // Ordenar: vigentes del más cercano al más lejano; pasados del más reciente al más antiguo
    return [...lista].sort((a, b) => {
      const claveA = `${a.fecha_evento}T${a.hora_inicio}`;
      const claveB = `${b.fecha_evento}T${b.hora_inicio}`;
      if (filtroVigencia === "pasados") {
        return claveB.localeCompare(claveA);
      }
      return claveA.localeCompare(claveB);
    });
  }, [eventos, filtroVigencia, busqueda, filtroTipo, filtroFecha]);

  const handleNuevoEvento = () => {
    setEventoEditar(null);
    setModalAbierto(true);
  };

  const handleEditar = (evento: Evento) => {
    setEventoEditar(evento);
    setModalAbierto(true);
  };

  const handleEliminar = async (id: number) => {
    const confirmar = window.confirm(
      `¿Estás seguro de que deseas eliminar el evento con ID #${id}? Se liberará el horario reservado en la cancha.`
    );

    if (!confirmar) return;

    try {
      await onEliminarEvento(id);
    } catch (error) {
      console.error("Error al eliminar evento:", error);
    }
  };

  const handleSubmit = async (data: CreateEventoDTO) => {
    try {
      if (eventoEditar) {
        await onActualizarEvento(eventoEditar.id_evento, data);
      } else {
        await onCrearEvento(data);
      }

      setModalAbierto(false);
      setEventoEditar(null);
    } catch (error) {
      console.error("Error al guardar evento:", error);
      throw error;
    }
  };

  const controlStyle: React.CSSProperties = {
    backgroundColor: "var(--color-bg-elevated)",
    color: "var(--color-text)",
    border: "1px solid var(--color-border)",
    borderRadius: "6px",
    padding: "8px 12px",
    fontSize: "14px",
  };

  const tabButtonStyle = (activo: boolean): React.CSSProperties => ({
    display: "inline-flex",
    alignItems: "center",
    gap: "8px",
    padding: "8px 14px",
    borderRadius: "6px",
    fontSize: "13px",
    fontWeight: 600,
    cursor: "pointer",
    border: activo
      ? "1px solid var(--primary, #10b981)"
      : "1px solid var(--color-border, #374151)",
    backgroundColor: activo
      ? "rgba(16, 185, 129, 0.14)"
      : "var(--color-bg-elevated)",
    color: activo ? "var(--primary, #10b981)" : "var(--color-text-dim)",
    transition: "all 0.15s ease",
  });

  const badgeCountStyle = (activo: boolean): React.CSSProperties => ({
    padding: "2px 7px",
    borderRadius: "999px",
    fontSize: "11px",
    fontWeight: 700,
    backgroundColor: activo
      ? "var(--primary, #10b981)"
      : "rgba(156, 163, 175, 0.2)",
    color: activo ? "#0b1320" : "var(--color-text)",
  });

  return (
    <AppLayout
      title="Gestión y Reserva de Eventos"
      subtitle="Programa eventos, reserva horarios de cancha, modifica o libera eventos del complejo deportivo."
    >
      {/* Barra de pestañas: Vigentes vs Historial de Pasados */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "12px",
          marginTop: "8px",
          marginBottom: "14px",
          paddingBottom: "12px",
          borderBottom: "1px solid var(--color-border)",
        }}
      >
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          <button
            type="button"
            onClick={() => setFiltroVigencia("vigentes")}
            style={tabButtonStyle(filtroVigencia === "vigentes")}
          >
            <span>Próximos / Vigentes</span>
            <span style={badgeCountStyle(filtroVigencia === "vigentes")}>
              {contadoresVigencia.vigentes}
            </span>
          </button>

          <button
            type="button"
            onClick={() => setFiltroVigencia("pasados")}
            style={tabButtonStyle(filtroVigencia === "pasados")}
          >
            <span>Historial de Pasados</span>
            <span style={badgeCountStyle(filtroVigencia === "pasados")}>
              {contadoresVigencia.pasados}
            </span>
          </button>

          <button
            type="button"
            onClick={() => setFiltroVigencia("todos")}
            style={tabButtonStyle(filtroVigencia === "todos")}
          >
            <span>Todos</span>
            <span style={badgeCountStyle(filtroVigencia === "todos")}>
              {contadoresVigencia.todos}
            </span>
          </button>
        </div>

        <button onClick={handleNuevoEvento} className="btn-success">
          <span style={{ fontSize: "16px", fontWeight: "bold" }}>+</span>
          {"  Reservar / Añadir Evento"}
        </button>
      </div>

      {/* Barra de filtros secundarios */}
      <div
        className="header-row"
        style={{
          marginBottom: "16px",
          flexWrap: "wrap",
          gap: "12px",
        }}
      >
        <h2 style={{ margin: 0, fontSize: "17px" }}>
          {filtroVigencia === "vigentes"
            ? `Eventos vigentes (${eventosFiltrados.length})`
            : filtroVigencia === "pasados"
              ? `Eventos finalizados (${eventosFiltrados.length})`
              : `Todos los eventos (${eventosFiltrados.length})`}
        </h2>

        <div
          style={{
            display: "flex",
            gap: "10px",
            alignItems: "center",
            flexWrap: "wrap",
          }}
        >
          <input
            type="text"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            placeholder="Buscar por evento, cancha, organizador o teléfono..."
            style={{ ...controlStyle, minWidth: "260px" }}
          />

          <select
            value={filtroTipo}
            onChange={(e) => setFiltroTipo(e.target.value)}
            style={controlStyle}
          >
            <option value="todos">Todos los tipos</option>
            {tiposDisponibles.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>

          <input
            type="date"
            value={filtroFecha}
            onChange={(e) => setFiltroFecha(e.target.value)}
            title="Filtrar por fecha exacta"
            style={controlStyle}
          />

          {(busqueda || filtroTipo !== "todos" || filtroFecha) && (
            <button
              type="button"
              onClick={() => {
                setBusqueda("");
                setFiltroTipo("todos");
                setFiltroFecha("");
              }}
              className="btn-secondary"
              style={{ padding: "8px 12px", fontSize: "13px" }}
            >
              Limpiar filtros
            </button>
          )}
        </div>
      </div>

      {loading && (
        <p style={{ color: "var(--color-text-dim)" }}>Cargando eventos...</p>
      )}

      {error && (
        <div
          style={{
            padding: "12px",
            backgroundColor: "rgba(220, 53, 69, 0.15)",
            color: "#c62828",
            border: "1px solid rgba(220, 53, 69, 0.5)",
            borderRadius: "6px",
            marginBottom: "15px",
          }}
        >
          {error}
        </div>
      )}

      {!loading && !error && eventosFiltrados.length === 0 && (
        <div
          style={{
            backgroundColor: "var(--color-bg-elevated)",
            border: "1px solid var(--color-border)",
            padding: "40px",
            borderRadius: "8px",
            textAlign: "center",
            color: "var(--color-text-dim)",
          }}
        >
          {eventos.length === 0
            ? "No hay eventos registrados en este momento."
            : filtroVigencia === "vigentes" &&
                !busqueda &&
                filtroTipo === "todos" &&
                !filtroFecha
              ? "No hay eventos próximos programados. Puedes consultar el 'Historial de Pasados' o programar uno nuevo."
              : filtroVigencia === "pasados" &&
                  !busqueda &&
                  filtroTipo === "todos" &&
                  !filtroFecha
                ? "Aún no hay eventos finalizados en el historial."
                : "No se encontraron eventos que coincidan con los filtros aplicados."}
        </div>
      )}

      {!loading && !error && eventosFiltrados.length > 0 && (
        <TablaEventosAdmin
          eventos={eventosFiltrados}
          onEditar={handleEditar}
          onEliminar={handleEliminar}
        />
      )}

      <EventoFormModal
        isOpen={modalAbierto}
        onClose={() => {
          setModalAbierto(false);
          setEventoEditar(null);
        }}
        onSubmit={handleSubmit}
        eventoEditar={eventoEditar}
      />
    </AppLayout>
  );
};

export default AdminEventosPage;
