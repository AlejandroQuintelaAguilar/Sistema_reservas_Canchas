import React, { useState, useEffect } from "react";
import type {
  Evento,
  CreateEventoDTO,
  DisponibilidadEventoResponse,
  DisponibilidadSemanalResponse,
} from "../../types/evento.types";
import { Modal } from "../common/Modal";
import {
  CUPOS_MAX,
  HORA_ATENCION_MAX,
  HORA_ATENCION_MIN,
  esNumeroValido,
  horaFinPosterior,
} from "../../utils/validaciones";
import { api } from "../../services/api";
import { eventoService } from "../../services/eventoService";
import { CalendarioDisponibilidadEvento } from "./CalendarioDisponibilidadEvento";

interface CanchaOption {
  id?: number;
  id_cancha?: number;
  nombre?: string;
  nombre_cancha?: string;
  deporte?: string | null;
  tipo_deporte?: string | null;
  estado?: string;
}

interface EventoFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: CreateEventoDTO) => Promise<void>;
  eventoEditar: Evento | null;
}

const TIPOS_EVENTO_ESTANDAR = [
  "Servicio Social",
  "Torneo",
  "Deportivo",
  "Social",
  "Taller",
  "Comunitario",
];

const DIAS_SEMANA_ES = [
  "Domingo",
  "Lunes",
  "Martes",
  "Miércoles",
  "Jueves",
  "Viernes",
  "Sábado",
];

const getNombreDiaSemana = (fechaISO: string): string => {
  if (!fechaISO) return "día";
  const partes = fechaISO.split("-").map(Number);
  if (partes.length !== 3) return "día";
  const d = new Date(partes[0], partes[1] - 1, partes[2]);
  return DIAS_SEMANA_ES[d.getDay()] || "día";
};

/**
 * Obtiene la fecha actual en la zona horaria local del usuario en formato YYYY-MM-DD,
 * evitando el desfase UTC de toISOString() en horas nocturnas.
 */
const getFechaLocalISO = (): string => {
  const ahora = new Date();
  const anio = ahora.getFullYear();
  const mes = String(ahora.getMonth() + 1).padStart(2, "0");
  const dia = String(ahora.getDate()).padStart(2, "0");
  return `${anio}-${mes}-${dia}`;
};

export const EventoFormModal: React.FC<EventoFormModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  eventoEditar,
}) => {
  const [formData, setFormData] = useState<CreateEventoDTO>({
    nombre_evento: "",
    tipo_evento: "Servicio Social",
    fecha_evento: getFechaLocalISO(),
    hora_inicio: "09:00",
    hora_fin: "11:00",
    cupo_maximo: 20,
    organizador: "",
    contacto: "",
    descripcion: "",
    id_cancha: 1,
    ids_canchas: [1],
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [canchas, setCanchas] = useState<CanchaOption[]>([]);
  const [cargandoCanchas, setCargandoCanchas] = useState(false);

  const [disponibilidad, setDisponibilidad] =
    useState<DisponibilidadEventoResponse | null>(null);
  const [verificandoDisp, setVerificandoDisp] = useState(false);

  // Estado para repetición semanal (1 = evento único, 2..12 = N semanas consecutivas)
  const [repeticionesSemanales, setRepeticionesSemanales] = useState<number>(1);
  const [horariosPersonalizados, setHorariosPersonalizados] = useState<
    Record<string, { hora_inicio: string; hora_fin: string }>
  >({});
  const [disponibilidadSemanal, setDisponibilidadSemanal] =
    useState<DisponibilidadSemanalResponse | null>(null);
  const [verificandoSerie, setVerificandoSerie] = useState(false);
  const [errorVerificacionSerie, setErrorVerificacionSerie] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setCargandoCanchas(true);
      api
        .get<CanchaOption[]>("/canchas")
        .then((res: { data: CanchaOption[] }) => {
          if (Array.isArray(res.data)) {
            setCanchas(res.data);
            if (!eventoEditar && res.data.length > 0) {
              const canchaOperativa = res.data.find(
                (c) =>
                  c.estado !== "fuera_servicio" && c.estado !== "mantenimiento"
              );
              const idSeleccionado = canchaOperativa
                ? (canchaOperativa.id_cancha ?? canchaOperativa.id ?? 1)
                : (res.data[0].id_cancha ?? res.data[0].id ?? 1);
              setFormData((prev) => ({
                ...prev,
                id_cancha: idSeleccionado,
                ids_canchas: [idSeleccionado],
              }));
            }
          }
        })
        .catch((err: unknown) =>
          console.error("Error al cargar las canchas:", err)
        )
        .finally(() => setCargandoCanchas(false));
    }
  }, [isOpen, eventoEditar]);

  useEffect(() => {
    if (eventoEditar) {
      const canchasIniciales =
        eventoEditar.ids_canchas && eventoEditar.ids_canchas.length > 0
          ? eventoEditar.ids_canchas
          : [eventoEditar.id_cancha];
      setFormData({
        nombre_evento: eventoEditar.nombre_evento,
        tipo_evento: eventoEditar.tipo_evento || "Servicio Social",
        fecha_evento: eventoEditar.fecha_evento,
        hora_inicio: eventoEditar.hora_inicio,
        hora_fin: eventoEditar.hora_fin,
        cupo_maximo: eventoEditar.cupo_maximo || 20,
        organizador: eventoEditar.organizador || "",
        contacto: eventoEditar.contacto || "",
        descripcion: eventoEditar.descripcion || "",
        id_cancha: canchasIniciales[0],
        ids_canchas: canchasIniciales,
      });
    } else {
      const canchaOperativa = canchas.find(
        (c) => c.estado !== "fuera_servicio" && c.estado !== "mantenimiento"
      );
      const defaultCanchaId = canchaOperativa
        ? (canchaOperativa.id_cancha ?? canchaOperativa.id ?? 1)
        : canchas.length > 0
          ? (canchas[0].id_cancha ?? canchas[0].id ?? 1)
          : 1;

      setFormData({
        nombre_evento: "",
        tipo_evento: "Servicio Social",
        fecha_evento: getFechaLocalISO(),
        hora_inicio: "09:00",
        hora_fin: "11:00",
        cupo_maximo: 20,
        organizador: "",
        contacto: "",
        descripcion: "",
        id_cancha: defaultCanchaId,
        ids_canchas: [defaultCanchaId],
      });
    }
    setRepeticionesSemanales(1);
    setHorariosPersonalizados({});
    setDisponibilidadSemanal(null);
    setErrorVerificacionSerie(null);
    setError(null);
    setDisponibilidad(null);
  }, [eventoEditar, isOpen]);

  // Limpiar overrides cuando cambie la fecha inicial o el horario base
  useEffect(() => {
    setHorariosPersonalizados({});
  }, [
    formData.fecha_evento,
    formData.hora_inicio,
    formData.hora_fin,
    repeticionesSemanales,
  ]);

  const canchasSeleccionadas = formData.ids_canchas ?? [formData.id_cancha];
  const esModoSemanal = !eventoEditar && repeticionesSemanales > 1;

  // Verificación preventiva de disponibilidad (evento único)
  useEffect(() => {
    if (
      !isOpen ||
      esModoSemanal ||
      canchasSeleccionadas.length === 0 ||
      !formData.fecha_evento ||
      !formData.hora_inicio ||
      !formData.hora_fin
    ) {
      setDisponibilidad(null);
      return;
    }

    let cancelado = false;
    setVerificandoDisp(true);

    const timer = setTimeout(() => {
      eventoService
        .checkDisponibilidad({
          ids_canchas: canchasSeleccionadas,
          fecha_evento: formData.fecha_evento,
          hora_inicio: formData.hora_inicio,
          hora_fin: formData.hora_fin,
          excluir_id: eventoEditar?.id_evento,
        })
        .then((res) => {
          if (!cancelado) {
            setDisponibilidad(res);
          }
        })
        .catch(() => {
          if (!cancelado) {
            setDisponibilidad(null);
          }
        })
        .finally(() => {
          if (!cancelado) {
            setVerificandoDisp(false);
          }
        });
    }, 200);

    return () => {
      cancelado = true;
      clearTimeout(timer);
    };
  }, [
    isOpen,
    esModoSemanal,
    canchasSeleccionadas.join(","),
    formData.fecha_evento,
    formData.hora_inicio,
    formData.hora_fin,
    eventoEditar?.id_evento,
  ]);

  // Verificación de serie semanal cuando repeticionesSemanales > 1
  useEffect(() => {
    if (
      !isOpen ||
      !esModoSemanal ||
      canchasSeleccionadas.length === 0 ||
      !formData.fecha_evento ||
      !formData.hora_inicio ||
      !formData.hora_fin ||
      formData.hora_fin <= formData.hora_inicio
    ) {
      setDisponibilidadSemanal(null);
      setErrorVerificacionSerie(null);
      return;
    }

    let cancelado = false;
    setVerificandoSerie(true);
    setErrorVerificacionSerie(null);

    const timer = setTimeout(() => {
      eventoService
        .checkDisponibilidadSemanal({
          ids_canchas: canchasSeleccionadas,
          fecha_evento: formData.fecha_evento,
          hora_inicio: formData.hora_inicio,
          hora_fin: formData.hora_fin,
          repeticiones_semanales: repeticionesSemanales,
          horarios_personalizados: horariosPersonalizados,
        })
        .then((res) => {
          if (!cancelado) {
            setDisponibilidadSemanal(res);
            setErrorVerificacionSerie(null);
          }
        })
        .catch((err: any) => {
          if (!cancelado) {
            setDisponibilidadSemanal(null);
            const msg =
              err?.response?.data?.error ||
              "No se pudo conectar con el servidor para verificar las semanas.";
            setErrorVerificacionSerie(msg);
          }
        })
        .finally(() => {
          if (!cancelado) {
            setVerificandoSerie(false);
          }
        });
    }, 200);

    return () => {
      cancelado = true;
      clearTimeout(timer);
    };
  }, [
    isOpen,
    esModoSemanal,
    canchasSeleccionadas.join(","),
    formData.fecha_evento,
    formData.hora_inicio,
    formData.hora_fin,
    repeticionesSemanales,
    JSON.stringify(horariosPersonalizados),
  ]);

  const handleChange = (
    e: React.ChangeEvent<
      HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
    >
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: name === "cupo_maximo" ? Number(value) : value,
    }));
  };

  const handleToggleCancha = (idCancha: number) => {
    setFormData((prev) => {
      const actuales = prev.ids_canchas ?? [prev.id_cancha];
      const yaExiste = actuales.includes(idCancha);
      const nuevas = yaExiste
        ? actuales.filter((id) => id !== idCancha)
        : [...actuales, idCancha];
      return {
        ...prev,
        id_cancha: nuevas[0] ?? prev.id_cancha,
        ids_canchas: nuevas,
      };
    });
  };

  const handleSeleccionarTodasDisponibles = () => {
    const operativas = canchas
      .filter(
        (c) => c.estado !== "fuera_servicio" && c.estado !== "mantenimiento"
      )
      .map((c) => c.id_cancha ?? c.id ?? 0)
      .filter((id) => id > 0);

    if (operativas.length > 0) {
      setFormData((prev) => ({
        ...prev,
        id_cancha: operativas[0],
        ids_canchas: operativas,
      }));
    }
  };

  const handleElegirAlternativaSemana = (
    fechaISO: string,
    horaIni: string,
    horaFin: string
  ) => {
    setHorariosPersonalizados((prev) => ({
      ...prev,
      [fechaISO]: { hora_inicio: horaIni, hora_fin: horaFin },
    }));
  };

  const handleRestaurarHorarioBaseSemana = (fechaISO: string) => {
    setHorariosPersonalizados((prev) => {
      const copia = { ...prev };
      delete copia[fechaISO];
      return copia;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const hoy = getFechaLocalISO();
    if (!eventoEditar && formData.fecha_evento < hoy) {
      setError("La fecha del evento no puede ser anterior a la fecha actual.");
      return;
    }

    if (canchasSeleccionadas.length === 0) {
      setError("Debes seleccionar al menos una cancha para reservar el evento.");
      return;
    }

    if (!horaFinPosterior(formData.hora_inicio, formData.hora_fin)) {
      setError("La hora de fin debe ser estrictamente posterior a la hora de inicio.");
      return;
    }

    if (
      formData.hora_inicio < HORA_ATENCION_MIN ||
      formData.hora_fin > HORA_ATENCION_MAX
    ) {
      setError(
        `El evento debe quedar dentro del horario de atención (${HORA_ATENCION_MIN} a ${HORA_ATENCION_MAX}).`
      );
      return;
    }

    if (
      formData.cupo_maximo !== undefined &&
      formData.cupo_maximo !== null &&
      !esNumeroValido(formData.cupo_maximo, {
        min: 1,
        entero: true,
        max: CUPOS_MAX,
      })
    ) {
      setError(`El cupo debe ser un entero entre 1 y ${CUPOS_MAX}.`);
      return;
    }

    if (esModoSemanal) {
      if (!disponibilidadSemanal || !disponibilidadSemanal.todas_disponibles) {
        setError(
          "Una o más semanas tienen el horario ocupado. Selecciona un horario anterior o posterior disponible para las fechas en conflicto."
        );
        return;
      }
    } else if (disponibilidad && !disponibilidad.disponible) {
      setError(
        disponibilidad.motivo ||
          "Una o más canchas seleccionadas no están disponibles en ese horario."
      );
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const payload: CreateEventoDTO = {
        ...formData,
        id_cancha: canchasSeleccionadas[0],
        ids_canchas: canchasSeleccionadas,
      };

      if (esModoSemanal && disponibilidadSemanal) {
        payload.repeticiones_semanales = repeticionesSemanales;
        payload.sesiones_programadas = disponibilidadSemanal.sesiones.map(
          (s) => ({
            fecha_evento: s.fecha_evento,
            hora_inicio: s.hora_inicio,
            hora_fin: s.hora_fin,
          })
        );
      }

      await onSubmit(payload);
      onClose();
    } catch (err: any) {
      const errData = err?.response?.data;
      const errMsg = errData?.detalles
        ? Array.isArray(errData.detalles)
          ? errData.detalles.join(" ")
          : String(errData.detalles)
        : errData?.error || "Ocurrió un error al guardar el evento.";
      setError(errMsg);
    } finally {
      setLoading(false);
    }
  };

  const opcionesTipoEvento = React.useMemo(() => {
    const actual = formData.tipo_evento?.trim();
    if (actual && !TIPOS_EVENTO_ESTANDAR.includes(actual)) {
      return [actual, ...TIPOS_EVENTO_ESTANDAR];
    }
    return TIPOS_EVENTO_ESTANDAR;
  }, [formData.tipo_evento]);

  const nombreDiaActual = getNombreDiaSemana(formData.fecha_evento);

  const labelStyle = {
    display: "block",
    marginBottom: "4px",
    fontSize: "14px",
    fontWeight: 600,
    color: "var(--color-text, #111827)",
  };
  const inputStyle = {
    width: "100%",
    padding: "8px 10px",
    borderRadius: "6px",
    border: "1px solid var(--color-border, #e5e7eb)",
    backgroundColor: "var(--color-bg-elevated, #f1f1f4)",
    color: "var(--color-text, #111827)",
    boxSizing: "border-box" as const,
    fontSize: "14px",
  };

  // Cálculo explícito de la razón por la que el botón de reserva se inhabilita
  const razonBotonBloqueado = React.useMemo(() => {
    if (loading) return "Guardando evento...";
    if (canchasSeleccionadas.length === 0)
      return "Debes seleccionar al menos una cancha para reservar.";
    if (formData.hora_fin <= formData.hora_inicio)
      return "La hora de fin debe ser posterior a la de inicio.";

    if (esModoSemanal) {
      if (verificandoSerie)
        return "Comprobando la disponibilidad de todas las semanas...";
      if (!disponibilidadSemanal)
        return "Verificando disponibilidad de la serie semanal...";
      if (!disponibilidadSemanal.todas_disponibles) {
        return `Hay ${disponibilidadSemanal.semanas_con_conflicto} semana(s) con horario ocupado. Elige una hora anterior o posterior sugerida en la lista para continuar.`;
      }
    } else {
      if (verificandoDisp)
        return "Verificando disponibilidad de la cancha...";
      if (disponibilidad && !disponibilidad.disponible) {
        return disponibilidad.motivo || "El horario seleccionado no está disponible.";
      }
    }
    return null;
  }, [
    loading,
    canchasSeleccionadas.length,
    formData.hora_inicio,
    formData.hora_fin,
    esModoSemanal,
    verificandoSerie,
    disponibilidadSemanal,
    verificandoDisp,
    disponibilidad,
  ]);

  const botonSubmitDeshabilitado = Boolean(razonBotonBloqueado);

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      maxWidth="840px"
      title={
        eventoEditar
          ? "Modificar Reserva de Evento"
          : "Reservar Cancha(s) y Programar Evento"
      }
    >
      <form
        onSubmit={handleSubmit}
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "14px",
          fontFamily: "sans-serif",
          textAlign: "left",
        }}
      >
        {error && (
          <div
            style={{
              padding: "10px",
              backgroundColor: "#f8d7da",
              color: "#721c24",
              border: "1px solid #f5c6cb",
              borderRadius: "4px",
              fontSize: "14px",
            }}
          >
            {error}
          </div>
        )}

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "2fr 1fr",
            gap: "12px",
          }}
        >
          <div>
            <label style={labelStyle}>Nombre del Evento *</label>
            <input
              type="text"
              name="nombre_evento"
              value={formData.nombre_evento}
              onChange={handleChange}
              placeholder="Ej. Torneo Intercolegial / Jornada Solidaria"
              required
              style={inputStyle}
            />
          </div>

          <div>
            <label style={labelStyle}>Tipo de Evento *</label>
            <select
              name="tipo_evento"
              value={formData.tipo_evento || "Servicio Social"}
              onChange={handleChange}
              style={inputStyle}
            >
              {opcionesTipoEvento.map((tipo) => (
                <option key={tipo} value={tipo}>
                  {tipo}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Paso 1: Selector de una o múltiples canchas */}
        <div>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "6px",
              flexWrap: "wrap",
              gap: "6px",
            }}
          >
            <label style={{ ...labelStyle, marginBottom: 0 }}>
              1. Canchas a Reservar ({canchasSeleccionadas.length} seleccionada
              {canchasSeleccionadas.length === 1 ? "" : "s"}) *
            </label>
            {canchas.length > 1 && (
              <button
                type="button"
                onClick={handleSeleccionarTodasDisponibles}
                style={{
                  background: "none",
                  border: "none",
                  color: "var(--primary, #4f46e5)",
                  fontSize: "12px",
                  fontWeight: 600,
                  cursor: "pointer",
                  padding: 0,
                }}
              >
                Seleccionar todas las operativas
              </button>
            )}
          </div>

          {cargandoCanchas ? (
            <div style={{ ...inputStyle, color: "var(--color-text-dim)" }}>
              Cargando canchas disponibles...
            </div>
          ) : (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(195px, 1fr))",
                gap: "8px",
                maxHeight: "140px",
                overflowY: "auto",
                padding: "8px",
                borderRadius: "6px",
                border: "1px solid var(--color-border, #e5e7eb)",
                backgroundColor: "var(--color-bg-elevated, #f9fafb)",
              }}
            >
              {canchas.map((c) => {
                const id = c.id_cancha ?? c.id ?? 1;
                const nombre = c.nombre_cancha ?? c.nombre ?? `Cancha #${id}`;
                const deporte = c.tipo_deporte ?? c.deporte ?? "";
                const noOperativa =
                  c.estado === "fuera_servicio" || c.estado === "mantenimiento";
                const seleccionada = canchasSeleccionadas.includes(id);
                const estadoTag =
                  c.estado === "fuera_servicio"
                    ? "Fuera de servicio"
                    : c.estado === "mantenimiento"
                      ? "En mantenimiento"
                      : "";

                return (
                  <label
                    key={id}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      padding: "7px 10px",
                      borderRadius: "6px",
                      border: seleccionada
                        ? "1.5px solid var(--primary, #4f46e5)"
                        : "1px solid var(--color-border, #d1d5db)",
                      backgroundColor: seleccionada
                        ? "rgba(79, 70, 229, 0.1)"
                        : "var(--color-surface, #ffffff)",
                      opacity: noOperativa ? 0.55 : 1,
                      cursor: noOperativa ? "not-allowed" : "pointer",
                      fontSize: "13px",
                      userSelect: "none",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={seleccionada}
                      disabled={noOperativa}
                      onChange={() => handleToggleCancha(id)}
                      style={{ cursor: noOperativa ? "not-allowed" : "pointer" }}
                    />
                    <div style={{ lineHeight: 1.25 }}>
                      <div style={{ fontWeight: 600, color: "var(--color-text)" }}>
                        {nombre}
                      </div>
                      <div
                        style={{
                          fontSize: "11px",
                          color: noOperativa
                            ? "#dc2626"
                            : "var(--color-text-dim, #6b7280)",
                        }}
                      >
                        {deporte}
                        {estadoTag ? ` · ${estadoTag}` : ""}
                      </div>
                    </div>
                  </label>
                );
              })}
            </div>
          )}
        </div>

        {/* Paso 2: Calendario Interactivo y Selector Visual de Bloques Horarios */}
        <CalendarioDisponibilidadEvento
          idsCanchas={canchasSeleccionadas}
          fechaSeleccionada={formData.fecha_evento}
          horaInicio={formData.hora_inicio}
          horaFin={formData.hora_fin}
          excluirIdEvento={eventoEditar?.id_evento}
          onChangeFecha={(nuevaFecha) =>
            setFormData((prev) => ({ ...prev, fecha_evento: nuevaFecha }))
          }
          onChangeHorario={(nuevaHoraIni, nuevaHoraFin) =>
            setFormData((prev) => ({
              ...prev,
              hora_inicio: nuevaHoraIni,
              hora_fin: nuevaHoraFin,
            }))
          }
        />

        {/* Selector de Repetición Semanal (solo al crear nuevo evento) */}
        {!eventoEditar && (
          <div
            style={{
              padding: "12px",
              borderRadius: "8px",
              border: "1px solid var(--color-border, #e5e7eb)",
              backgroundColor: "var(--color-bg-elevated, #f9fafb)",
              display: "flex",
              flexDirection: "column",
              gap: "10px",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                flexWrap: "wrap",
                gap: "10px",
              }}
            >
              <div>
                <div
                  style={{
                    fontWeight: 600,
                    fontSize: "14px",
                    color: "var(--color-text, #111827)",
                  }}
                >
                  🔁 Programación Semanal Recurrente
                </div>
                <div
                  style={{
                    fontSize: "12px",
                    color: "var(--color-text-dim, #6b7280)",
                  }}
                >
                  Reserva automáticamente el mismo día ({nombreDiaActual}) durante
                  varias semanas seguidas.
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <label
                  style={{
                    fontSize: "13px",
                    fontWeight: 600,
                    color: "var(--color-text)",
                  }}
                >
                  Duración:
                </label>
                <select
                  value={repeticionesSemanales}
                  onChange={(e) =>
                    setRepeticionesSemanales(Number(e.target.value))
                  }
                  style={{
                    ...inputStyle,
                    width: "auto",
                    minWidth: "210px",
                    fontWeight: 600,
                  }}
                >
                  <option value={1}>1 semana (Evento único)</option>
                  {[2, 3, 4, 5, 6, 8, 10, 12].map((num) => (
                    <option key={num} value={num}>
                      {num} {nombreDiaActual}s seguidos ({num} semanas)
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Desglose interactivo de las N semanas y sugerencias de horario anterior/posterior */}
            {esModoSemanal && (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "8px",
                  marginTop: "4px",
                }}
              >
                {verificandoSerie ? (
                  <div
                    style={{
                      fontSize: "13px",
                      color: "var(--color-text-dim)",
                      padding: "8px 10px",
                      borderRadius: "6px",
                      backgroundColor: "rgba(59, 130, 246, 0.08)",
                      border: "1px solid rgba(59, 130, 246, 0.3)",
                    }}
                  >
                    ⏳ Verificando disponibilidad en las {repeticionesSemanales}{" "}
                    semanas...
                  </div>
                ) : disponibilidadSemanal ? (
                  <>
                    <div
                      style={{
                        padding: "8px 10px",
                        borderRadius: "6px",
                        fontSize: "13px",
                        fontWeight: 600,
                        backgroundColor:
                          disponibilidadSemanal.todas_disponibles
                            ? "rgba(16, 185, 129, 0.14)"
                            : "rgba(245, 158, 11, 0.15)",
                        border: disponibilidadSemanal.todas_disponibles
                          ? "1px solid rgba(16, 185, 129, 0.4)"
                          : "1px solid rgba(245, 158, 11, 0.5)",
                        color: disponibilidadSemanal.todas_disponibles
                          ? "#065f46"
                          : "#b45309",
                      }}
                    >
                      {disponibilidadSemanal.todas_disponibles
                        ? `✓ Las ${disponibilidadSemanal.repeticiones_semanales} semanas están listas y disponibles para reservar.`
                        : `⚠ ${disponibilidadSemanal.semanas_libres} de ${disponibilidadSemanal.repeticiones_semanales} semanas están libres. Elige una hora anterior o posterior para la(s) ${disponibilidadSemanal.semanas_con_conflicto} fecha(s) ocupada(s):`}
                    </div>

                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: "8px",
                        maxHeight: "230px",
                        overflowY: "auto",
                        paddingRight: "4px",
                      }}
                    >
                      {disponibilidadSemanal.sesiones.map((ses) => {
                        const mostrarOpcionesCambio =
                          !ses.disponible || ses.horario_ajustado;

                        return (
                          <div
                            key={ses.fecha_evento}
                            style={{
                              padding: "9px 12px",
                              borderRadius: "6px",
                              border: ses.disponible
                                ? "1px solid rgba(16, 185, 129, 0.4)"
                                : "1px solid rgba(220, 53, 69, 0.55)",
                              backgroundColor: ses.disponible
                                ? "rgba(16, 185, 129, 0.07)"
                                : "rgba(220, 53, 69, 0.08)",
                              fontSize: "13px",
                              display: "flex",
                              flexDirection: "column",
                              gap: "6px",
                            }}
                          >
                            <div
                              style={{
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "center",
                                flexWrap: "wrap",
                                gap: "6px",
                              }}
                            >
                              <div style={{ fontWeight: 600 }}>
                                Semana {ses.numero_semana} · {nombreDiaActual}{" "}
                                {ses.fecha_evento} ({ses.hora_inicio} -{" "}
                                {ses.hora_fin})
                              </div>

                              <div
                                style={{
                                  fontWeight: 600,
                                  fontSize: "12px",
                                  color: ses.disponible ? "#059669" : "#dc2626",
                                }}
                              >
                                {ses.disponible
                                  ? ses.horario_ajustado
                                    ? "✓ Horario alternativo aplicado"
                                    : "✓ Disponible"
                                  : "⚠ Horario ocupado"}
                              </div>
                            </div>

                            {!ses.disponible && ses.motivo && (
                              <div style={{ fontSize: "12px", color: "#b91c1c" }}>
                                {ses.motivo}
                              </div>
                            )}

                            {ses.horario_ajustado && ses.motivo_base && (
                              <div
                                style={{
                                  fontSize: "11.5px",
                                  color: "var(--color-text-dim)",
                                }}
                              >
                                Horario original ({ses.hora_inicio_base} -{" "}
                                {ses.hora_fin_base}) ocupado. Se reservará de{" "}
                                <strong>
                                  {ses.hora_inicio} a {ses.hora_fin}
                                </strong>
                                .
                              </div>
                            )}

                            {mostrarOpcionesCambio && (
                              <div
                                style={{
                                  display: "flex",
                                  flexDirection: "column",
                                  gap: "5px",
                                  marginTop: "2px",
                                }}
                              >
                                <div
                                  style={{
                                    fontSize: "12px",
                                    fontWeight: 600,
                                    color: "var(--color-text)",
                                  }}
                                >
                                  Opciones de horario libre para este{" "}
                                  {nombreDiaActual} ({ses.fecha_evento}):
                                </div>

                                {ses.alternativas_anteriores.length === 0 &&
                                ses.alternativas_posteriores.length === 0 ? (
                                  <div
                                    style={{
                                      fontSize: "12px",
                                      color: "#dc2626",
                                    }}
                                  >
                                    No quedan bloques libres de esa duración en
                                    esta fecha.
                                  </div>
                                ) : (
                                  <div
                                    style={{
                                      display: "flex",
                                      flexWrap: "wrap",
                                      gap: "6px",
                                    }}
                                  >
                                    {ses.alternativas_anteriores.map((alt) => {
                                      const activa =
                                        ses.hora_inicio === alt.hora_inicio &&
                                        ses.hora_fin === alt.hora_fin;
                                      return (
                                        <button
                                          key={`ant-${alt.hora_inicio}`}
                                          type="button"
                                          onClick={() =>
                                            handleElegirAlternativaSemana(
                                              ses.fecha_evento,
                                              alt.hora_inicio,
                                              alt.hora_fin
                                            )
                                          }
                                          style={{
                                            padding: "4px 9px",
                                            borderRadius: "5px",
                                            fontSize: "12px",
                                            fontWeight: 600,
                                            cursor: "pointer",
                                            border: activa
                                              ? "1.5px solid #059669"
                                              : "1px solid var(--color-border, #9ca3af)",
                                            backgroundColor: activa
                                              ? "#059669"
                                              : "var(--color-surface, #ffffff)",
                                            color: activa
                                              ? "#ffffff"
                                              : "var(--color-text, #111827)",
                                          }}
                                          title="Elegir este horario anterior"
                                        >
                                          ⬅ Anterior: {alt.hora_inicio} -{" "}
                                          {alt.hora_fin}
                                        </button>
                                      );
                                    })}

                                    {ses.alternativas_posteriores.map((alt) => {
                                      const activa =
                                        ses.hora_inicio === alt.hora_inicio &&
                                        ses.hora_fin === alt.hora_fin;
                                      return (
                                        <button
                                          key={`post-${alt.hora_inicio}`}
                                          type="button"
                                          onClick={() =>
                                            handleElegirAlternativaSemana(
                                              ses.fecha_evento,
                                              alt.hora_inicio,
                                              alt.hora_fin
                                            )
                                          }
                                          style={{
                                            padding: "4px 9px",
                                            borderRadius: "5px",
                                            fontSize: "12px",
                                            fontWeight: 600,
                                            cursor: "pointer",
                                            border: activa
                                              ? "1.5px solid #059669"
                                              : "1px solid var(--color-border, #9ca3af)",
                                            backgroundColor: activa
                                              ? "#059669"
                                              : "var(--color-surface, #ffffff)",
                                            color: activa
                                              ? "#ffffff"
                                              : "var(--color-text, #111827)",
                                          }}
                                          title="Elegir este horario posterior"
                                        >
                                          Posterior: {alt.hora_inicio} -{" "}
                                          {alt.hora_fin} ➡
                                        </button>
                                      );
                                    })}

                                    {ses.horario_ajustado && (
                                      <button
                                        type="button"
                                        onClick={() =>
                                          handleRestaurarHorarioBaseSemana(
                                            ses.fecha_evento
                                          )
                                        }
                                        style={{
                                          padding: "4px 8px",
                                          borderRadius: "5px",
                                          fontSize: "11.5px",
                                          cursor: "pointer",
                                          border:
                                            "1px solid var(--color-border)",
                                          backgroundColor: "transparent",
                                          color: "var(--color-text-dim)",
                                        }}
                                      >
                                        Restablecer ({ses.hora_inicio_base} -{" "}
                                        {ses.hora_fin_base})
                                      </button>
                                    )}
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </>
                ) : (
                  <div
                    style={{
                      fontSize: "12.5px",
                      color: "#b45309",
                      padding: "8px 10px",
                      borderRadius: "6px",
                      backgroundColor: "rgba(245, 158, 11, 0.1)",
                      border: "1px solid rgba(245, 158, 11, 0.3)",
                    }}
                  >
                    {errorVerificacionSerie ||
                      (formData.hora_fin <= formData.hora_inicio
                        ? "La hora de fin debe ser posterior a la de inicio."
                        : "No se pudo verificar la serie de semanas. Revisa que el horario base sea válido.")}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Estado de disponibilidad cuando es un evento de 1 sola semana */}
        {!esModoSemanal &&
          (verificandoDisp ||
            disponibilidad ||
            canchasSeleccionadas.length === 0) && (
            <div
              style={{
                padding: "9px 12px",
                borderRadius: "6px",
                fontSize: "13px",
                border:
                  canchasSeleccionadas.length === 0
                    ? "1px solid rgba(220, 53, 69, 0.5)"
                    : verificarBordeDisponibilidad(
                        verificandoDisp,
                        disponibilidad
                      ),
                backgroundColor:
                  canchasSeleccionadas.length === 0
                    ? "rgba(220, 53, 69, 0.12)"
                    : verificarFondoDisponibilidad(
                        verificandoDisp,
                        disponibilidad
                      ),
                color:
                  canchasSeleccionadas.length === 0
                    ? "#991b1b"
                    : verificarTextoDisponibilidad(
                        verificandoDisp,
                        disponibilidad
                      ),
              }}
            >
              {canchasSeleccionadas.length === 0
                ? "⚠ Selecciona al menos una cancha para el evento."
                : verificandoDisp
                  ? "Verificando disponibilidad de la(s) cancha(s)..."
                  : disponibilidad?.disponible
                    ? `✓ ${disponibilidad.mensaje || "Horario disponible para reservar el evento."}`
                    : `⚠ ${disponibilidad?.motivo || "Horario no disponible."}`}
            </div>
          )}

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
            gap: "12px",
          }}
        >
          <div>
            <label style={labelStyle}>Organizador / Solicitante</label>
            <input
              type="text"
              name="organizador"
              value={formData.organizador}
              onChange={handleChange}
              placeholder="Institución, club o encargado"
              style={inputStyle}
            />
          </div>

          <div>
            <label style={labelStyle}>WhatsApp / Teléfono (Opcional)</label>
            <input
              type="tel"
              name="contacto"
              value={formData.contacto || ""}
              onChange={handleChange}
              placeholder="Ej. 77712345 o +591 77712345"
              style={inputStyle}
            />
          </div>

          <div>
            <label style={labelStyle}>Cupo Máximo *</label>
            <input
              type="number"
              name="cupo_maximo"
              value={formData.cupo_maximo || ""}
              onChange={handleChange}
              required
              min={1}
              max={CUPOS_MAX}
              step={1}
              style={inputStyle}
            />
          </div>
        </div>

        <div>
          <label style={labelStyle}>Descripción</label>
          <textarea
            name="descripcion"
            value={formData.descripcion}
            onChange={handleChange}
            rows={2}
            style={{ ...inputStyle, fontFamily: "inherit" }}
          />
        </div>

        {/* Mensaje explícito cuando el botón de guardar esté deshabilitado */}
        {razonBotonBloqueado && (
          <div
            style={{
              padding: "8px 12px",
              borderRadius: "6px",
              fontSize: "12.5px",
              backgroundColor: "rgba(239, 68, 68, 0.08)",
              border: "1px solid rgba(239, 68, 68, 0.3)",
              color: "#b91c1c",
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            <span>ℹ</span>
            <span>
              <strong>No se puede reservar aún:</strong> {razonBotonBloqueado}
            </span>
          </div>
        )}

        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            gap: "10px",
            marginTop: "6px",
          }}
        >
          <button type="button" onClick={onClose} className="btn-secondary">
            Cancelar
          </button>
          <button
            type="submit"
            disabled={botonSubmitDeshabilitado}
            className="btn-primary"
            title={razonBotonBloqueado || undefined}
          >
            {loading
              ? "Guardando..."
              : eventoEditar
                ? "Actualizar Evento"
                : esModoSemanal
                  ? `Reservar Serie (${repeticionesSemanales} Semanas)`
                  : "Reservar y Crear Evento"}
          </button>
        </div>
      </form>
    </Modal>
  );
};

function verificarBordeDisponibilidad(
  verificando: boolean,
  disp: DisponibilidadEventoResponse | null
) {
  if (verificando) return "1px solid var(--color-border, #d1d5db)";
  if (disp?.disponible) return "1px solid rgba(16, 185, 129, 0.45)";
  return "1px solid rgba(220, 53, 69, 0.5)";
}

function verificarFondoDisponibilidad(
  verificando: boolean,
  disp: DisponibilidadEventoResponse | null
) {
  if (verificando) return "var(--color-bg-elevated, #f3f4f6)";
  if (disp?.disponible) return "rgba(16, 185, 129, 0.12)";
  return "rgba(220, 53, 69, 0.12)";
}

function verificarTextoDisponibilidad(
  verificando: boolean,
  disp: DisponibilidadEventoResponse | null
) {
  if (verificando) return "var(--color-text-dim, #4b5563)";
  if (disp?.disponible) return "#065f46";
  return "#991b1b";
}

export default EventoFormModal;
