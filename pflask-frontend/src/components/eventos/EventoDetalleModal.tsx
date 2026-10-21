import React from "react";
import { buildWhatsAppEventoUrl, type Evento } from "../../types/evento.types";
import { Modal } from "../common/Modal";
import { Badge } from "../common/Badge";

interface EventoDetalleModalProps {
  evento: Evento | null;
  isOpen: boolean;
  onClose: () => void;
}

export const EventoDetalleModal: React.FC<EventoDetalleModalProps> = ({
  evento,
  isOpen,
  onClose,
}) => {
  if (!evento) return null;

  const listaCanchas =
    evento.nombres_canchas && evento.nombres_canchas.length > 0
      ? evento.nombres_canchas
      : [evento.nombre_cancha || `Cancha #${evento.id_cancha}`];

  const whatsappUrl = buildWhatsAppEventoUrl(evento);

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={evento.nombre_evento}>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "15px",
          fontFamily: "sans-serif",
          textAlign: "left",
        }}
      >
        <div
          style={{
            display: "flex",
            gap: "8px",
            alignItems: "center",
            flexWrap: "wrap",
          }}
        >
          <Badge variant="primary">{evento.tipo_evento || "Evento Social"}</Badge>
          {evento.cupo_maximo && (
            <Badge variant="info">Cupo: {evento.cupo_maximo} personas</Badge>
          )}
          <Badge variant="neutral">
            {listaCanchas.length === 1
              ? "1 cancha reservada"
              : `${listaCanchas.length} canchas reservadas`}
          </Badge>
        </div>

        <div>
          <h4
            style={{
              margin: "0 0 6px 0",
              color: "var(--color-text-dim, #6b7280)",
              fontSize: "0.85rem",
              textTransform: "uppercase",
            }}
          >
            Descripción
          </h4>
          <p
            style={{
              margin: 0,
              color: "var(--color-text, #111827)",
              lineHeight: 1.5,
              fontSize: "0.95rem",
            }}
          >
            {evento.descripcion ||
              "No se ha proporcionado una descripción detallada para este evento."}
          </p>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "12px",
            backgroundColor: "var(--color-bg-elevated, #f1f1f4)",
            border: "1px solid var(--color-border, #e5e7eb)",
            padding: "15px",
            borderRadius: "8px",
          }}
        >
          <div>
            <span
              style={{
                color: "var(--color-text-dim, #6b7280)",
                fontSize: "0.8rem",
                display: "block",
              }}
            >
              Fecha
            </span>
            <strong style={{ color: "var(--color-text, #111827)" }}>
              {evento.fecha_evento}
            </strong>
          </div>
          <div>
            <span
              style={{
                color: "var(--color-text-dim, #6b7280)",
                fontSize: "0.8rem",
                display: "block",
              }}
            >
              Horario
            </span>
            <strong style={{ color: "var(--color-text, #111827)" }}>
              {evento.hora_inicio} - {evento.hora_fin}
            </strong>
          </div>
          <div style={{ gridColumn: "1 / -1" }}>
            <span
              style={{
                color: "var(--color-text-dim, #6b7280)",
                fontSize: "0.8rem",
                display: "block",
                marginBottom: "4px",
              }}
            >
              Cancha(s) Asignada(s)
            </span>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
              {listaCanchas.map((canchaNombre, idx) => (
                <Badge key={idx} variant="info">
                  {canchaNombre}
                </Badge>
              ))}
            </div>
          </div>
          <div>
            <span
              style={{
                color: "var(--color-text-dim, #6b7280)",
                fontSize: "0.8rem",
                display: "block",
              }}
            >
              Organizador
            </span>
            <strong style={{ color: "var(--color-text, #111827)" }}>
              {evento.organizador || "Comunidad / Club"}
            </strong>
          </div>
          <div>
            <span
              style={{
                color: "var(--color-text-dim, #6b7280)",
                fontSize: "0.8rem",
                display: "block",
              }}
            >
              Contacto / WhatsApp
            </span>
            <strong style={{ color: "var(--color-text, #111827)" }}>
              {evento.contacto || "No especificado"}
            </strong>
          </div>
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "10px",
            marginTop: "10px",
          }}
        >
          {whatsappUrl ? (
            <a
              href={whatsappUrl}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "9px 16px",
                borderRadius: "6px",
                backgroundColor: "#25D366",
                color: "#ffffff",
                fontWeight: 600,
                fontSize: "0.9rem",
                textDecoration: "none",
                boxShadow: "0 2px 6px rgba(37, 211, 102, 0.25)",
              }}
            >
              <span>💬</span> Más información por WhatsApp
            </a>
          ) : (
            <div />
          )}

          <button
            onClick={onClose}
            className="btn-secondary"
            style={{ padding: "8px 20px", borderRadius: "6px" }}
          >
            Cerrar
          </button>
        </div>
      </div>
    </Modal>
  );
};

export default EventoDetalleModal;
