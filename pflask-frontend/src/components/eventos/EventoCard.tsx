import React from "react";
import { buildWhatsAppEventoUrl, type Evento } from "../../types/evento.types";
import { Badge } from "../common/Badge";

interface EventoCardProps {
  evento: Evento;
  onVerDetalles: (evento: Evento) => void;
}

export const EventoCard: React.FC<EventoCardProps> = ({
  evento,
  onVerDetalles,
}) => {
  const whatsappUrl = buildWhatsAppEventoUrl(evento);

  return (
    <div
      style={{
        backgroundColor: "var(--color-surface, #ffffff)",
        borderRadius: "12px",
        border: "1px solid var(--color-border, #e5e7eb)",
        padding: "20px",
        display: "flex",
        flexDirection: "column",
        gap: "12px",
        boxShadow: "var(--shadow, 0 4px 20px rgba(17, 24, 39, 0.06))",
        fontFamily: "sans-serif",
        textAlign: "left",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <Badge variant="primary">{evento.tipo_evento || "Evento Social"}</Badge>
        <span
          style={{
            fontSize: "0.85rem",
            color: "var(--color-text-dim, #6b7280)",
          }}
        >
          Fecha: {evento.fecha_evento}
        </span>
      </div>

      <h4
        style={{
          margin: 0,
          fontSize: "1.2rem",
          color: "var(--color-text, #111827)",
          fontWeight: 600,
        }}
      >
        {evento.nombre_evento}
      </h4>

      <p
        style={{
          margin: 0,
          fontSize: "0.95rem",
          color: "var(--color-text-dim, #6b7280)",
          lineHeight: 1.5,
        }}
      >
        {evento.descripcion
          ? evento.descripcion.length > 90
            ? evento.descripcion.substring(0, 90) + "..."
            : evento.descripcion
          : "Sin descripción disponible."}
      </p>

      <div
        style={{
          fontSize: "0.85rem",
          color: "var(--color-text-dim, #6b7280)",
          marginTop: "auto",
          display: "flex",
          flexDirection: "column",
          gap: "4px",
        }}
      >
        <div>
          Horario:{" "}
          <strong style={{ color: "var(--color-text, #111827)" }}>
            {evento.hora_inicio} - {evento.hora_fin}
          </strong>
        </div>
        {evento.nombre_cancha && (
          <div>
            Cancha(s):{" "}
            <strong style={{ color: "var(--color-text, #111827)" }}>
              {evento.nombre_cancha}
            </strong>
          </div>
        )}
        {evento.contacto && (
          <div>
            Contacto:{" "}
            <strong style={{ color: "var(--color-text, #111827)" }}>
              {evento.contacto}
            </strong>
          </div>
        )}
      </div>

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "8px",
          marginTop: "8px",
        }}
      >
        <button
          onClick={() => onVerDetalles(evento)}
          className="btn-primary"
          style={{
            padding: "10px 15px",
            fontSize: "0.9rem",
            borderRadius: "6px",
            width: "100%",
          }}
        >
          Ver Más Detalles
        </button>

        {whatsappUrl && (
          <a
            href={whatsappUrl}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "6px",
              padding: "9px 15px",
              fontSize: "0.88rem",
              fontWeight: 600,
              borderRadius: "6px",
              backgroundColor: "#25D366",
              color: "#ffffff",
              textDecoration: "none",
              textAlign: "center",
              boxShadow: "0 2px 6px rgba(37, 211, 102, 0.25)",
            }}
          >
            <span>💬</span> Más información por WhatsApp
          </a>
        )}
      </div>
    </div>
  );
};

export default EventoCard;
