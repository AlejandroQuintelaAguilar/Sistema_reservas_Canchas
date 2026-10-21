import React from "react";
import type { Evento } from "../../types/evento.types";
import { Badge } from "../common/Badge";

interface TablaEventosAdminProps {
  eventos: Evento[];
  onEditar: (evento: Evento) => void;
  onEliminar: (id: number) => void;
}

export const TablaEventosAdmin: React.FC<TablaEventosAdminProps> = ({
  eventos,
  onEditar,
  onEliminar,
}) => {
  return (
    <div
      className="tabla-wrapper"
      style={{ overflowX: "auto", width: "100%", fontFamily: "sans-serif" }}
    >
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Nombre del Evento</th>
            <th>Tipo</th>
            <th>Fecha</th>
            <th>Horario</th>
            <th>Cancha(s) Reservada(s)</th>
            <th>Contacto</th>
            <th>Cupo</th>
            <th style={{ textAlign: "center" }}>Acciones</th>
          </tr>
        </thead>
        <tbody>
          {eventos.length === 0 ? (
            <tr>
              <td
                colSpan={9}
                style={{
                  textAlign: "center",
                  padding: "20px",
                  color: "var(--color-text-dim, #6b7280)",
                }}
              >
                No hay eventos registrados en este momento.
              </td>
            </tr>
          ) : (
            eventos.map((e) => {
              const listaNombres =
                e.nombres_canchas && e.nombres_canchas.length > 0
                  ? e.nombres_canchas
                  : [e.nombre_cancha || `Cancha #${e.id_cancha}`];

              return (
                <tr key={e.id_evento}>
                  <td style={{ color: "var(--color-text-dim, #6b7280)" }}>
                    {e.id_evento}
                  </td>
                  <td
                    style={{
                      fontWeight: 600,
                      color: "var(--color-text, #111827)",
                    }}
                  >
                    {e.nombre_evento}
                  </td>
                  <td>
                    <Badge variant="primary">{e.tipo_evento || "Social"}</Badge>
                  </td>
                  <td style={{ color: "var(--color-text-dim, #6b7280)" }}>
                    {e.fecha_evento}
                  </td>
                  <td style={{ color: "var(--color-text-dim, #6b7280)" }}>
                    {e.hora_inicio} - {e.hora_fin}
                  </td>
                  <td style={{ color: "var(--color-text-dim, #6b7280)" }}>
                    <div
                      style={{
                        display: "flex",
                        flexWrap: "wrap",
                        gap: "4px",
                      }}
                    >
                      {listaNombres.map((nombre, idx) => (
                        <Badge key={idx} variant="info">
                          {nombre}
                        </Badge>
                      ))}
                    </div>
                  </td>
                  <td style={{ color: "var(--color-text-dim, #6b7280)" }}>
                    {e.contacto || "—"}
                  </td>
                  <td style={{ color: "var(--color-text-dim, #6b7280)" }}>
                    {e.cupo_maximo || "Sin límite"}
                  </td>
                  <td style={{ textAlign: "center" }}>
                    <div className="acciones">
                      <button
                        onClick={() => onEditar(e)}
                        className="btn-primary btn-sm"
                      >
                        Editar
                      </button>
                      <button
                        onClick={() => onEliminar(e.id_evento)}
                        className="btn-danger btn-sm"
                      >
                        Eliminar
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
};

export default TablaEventosAdmin;
