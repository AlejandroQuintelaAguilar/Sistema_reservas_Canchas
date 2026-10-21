import React, { useState, useMemo } from "react";
import type { Evento, CreateEventoDTO } from "../types/evento.types";
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

  // Filtros de búsqueda rápida para Administrador y Empleado
  const [busqueda, setBusqueda] = useState("");
  const [filtroTipo, setFiltroTipo] = useState("todos");
  const [filtroFecha, setFiltroFecha] = useState("");

  const tiposDisponibles = useMemo(() => {
    return Array.from(
      new Set(eventos.map((e) => e.tipo_evento).filter(Boolean))
    ) as string[];
  }, [eventos]);

  const eventosFiltrados = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    return eventos.filter((ev) => {
      const coincideTexto =
        !q ||
        ev.nombre_evento.toLowerCase().includes(q) ||
        (ev.nombre_cancha || "").toLowerCase().includes(q) ||
        (ev.organizador || "").toLowerCase().includes(q);
      const coincideTipo =
        filtroTipo === "todos" || ev.tipo_evento === filtroTipo;
      const coincideFecha = !filtroFecha || ev.fecha_evento === filtroFecha;
      return coincideTexto && coincideTipo && coincideFecha;
    });
  }, [eventos, busqueda, filtroTipo, filtroFecha]);

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

  return (
    <AppLayout
      title="Gestión y Reserva de Eventos"
      subtitle="Programa eventos, reserva horarios de cancha, modifica o libera eventos del complejo deportivo."
    >
      <div
        className="header-row"
        style={{
          marginTop: "8px",
          marginBottom: "16px",
          flexWrap: "wrap",
          gap: "12px",
        }}
      >
        <h2 style={{ margin: 0, fontSize: "18px" }}>
          Eventos registrados ({eventosFiltrados.length})
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
            placeholder="Buscar por evento, cancha u organizador..."
            style={{ ...controlStyle, minWidth: "240px" }}
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
            title="Filtrar por fecha"
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
              Limpiar
            </button>
          )}

          <button onClick={handleNuevoEvento} className="btn-success">
            <span style={{ fontSize: "16px", fontWeight: "bold" }}>+</span>
            {"  Reservar / Añadir Evento"}
          </button>
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
