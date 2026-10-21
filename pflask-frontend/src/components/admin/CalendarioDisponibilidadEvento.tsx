import React, { useState, useEffect, useMemo } from "react";
import type {
  AgendaDisponibilidadResponse,
  BloqueHorarioAgenda,
} from "../../types/evento.types";
import { eventoService } from "../../services/eventoService";

interface CalendarioDisponibilidadEventoProps {
  idsCanchas: number[];
  fechaSeleccionada: string;
  horaInicio: string;
  horaFin: string;
  excluirIdEvento?: number;
  onChangeFecha: (nuevaFecha: string) => void;
  onChangeHorario: (nuevaHoraInicio: string, nuevaHoraFin: string) => void;
}

const NOMBRES_MESES = [
  "Enero",
  "Febrero",
  "Marzo",
  "Abril",
  "Mayo",
  "Junio",
  "Julio",
  "Agosto",
  "Septiembre",
  "Octubre",
  "Noviembre",
  "Diciembre",
];

const DIAS_SEMANA = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

const getFechaLocalISO = (): string => {
  const ahora = new Date();
  const anio = ahora.getFullYear();
  const mes = String(ahora.getMonth() + 1).padStart(2, "0");
  const dia = String(ahora.getDate()).padStart(2, "0");
  return `${anio}-${mes}-${dia}`;
};

export const CalendarioDisponibilidadEvento: React.FC<
  CalendarioDisponibilidadEventoProps
> = ({
  idsCanchas,
  fechaSeleccionada,
  horaInicio,
  horaFin,
  excluirIdEvento,
  onChangeFecha,
  onChangeHorario,
}) => {
  const hoyISO = useMemo(() => getFechaLocalISO(), []);

  // Mes visible en el calendario (YYYY-MM)
  const [mesVisible, setMesVisible] = useState<string>(() =>
    fechaSeleccionada && fechaSeleccionada.length >= 7
      ? fechaSeleccionada.slice(0, 7)
      : hoyISO.slice(0, 7)
  );

  const [agenda, setAgenda] = useState<AgendaDisponibilidadResponse | null>(
    null
  );
  const [cargandoAgenda, setCargandoAgenda] = useState(false);
  const [anclaInicio, setAnclaInicio] = useState<string | null>(null);
  const [avisoRango, setAvisoRango] = useState<string | null>(null);

  useEffect(() => {
    if (fechaSeleccionada && fechaSeleccionada.length >= 7) {
      setMesVisible(fechaSeleccionada.slice(0, 7));
    }
  }, [fechaSeleccionada]);

  useEffect(() => {
    if (!idsCanchas || idsCanchas.length === 0 || !fechaSeleccionada) {
      setAgenda(null);
      return;
    }

    let cancelado = false;
    setCargandoAgenda(true);

    eventoService
      .getAgendaDisponibilidad({
        ids_canchas: idsCanchas,
        fecha: fechaSeleccionada,
        mes: mesVisible,
        excluir_id: excluirIdEvento,
      })
      .then((res) => {
        if (!cancelado) {
          setAgenda(res);
        }
      })
      .catch(() => {
        if (!cancelado) {
          setAgenda(null);
        }
      })
      .finally(() => {
        if (!cancelado) {
          setCargandoAgenda(false);
        }
      });

    return () => {
      cancelado = true;
    };
  }, [idsCanchas.join(","), fechaSeleccionada, mesVisible, excluirIdEvento]);

  // Construcción de celdas del calendario mensual
  const { anioActual, mesIdx, celdasMes } = useMemo(() => {
    const [yStr, mStr] = mesVisible.split("-");
    const anio = Number(yStr) || new Date().getFullYear();
    const mes = (Number(mStr) || 1) - 1; // 0..11

    const primerDia = new Date(anio, mes, 1);
    const ultimoDia = new Date(anio, mes + 1, 0);
    const totalDias = ultimoDia.getDate();

    // Lunes = 0 ... Domingo = 6
    const offsetInicio = (primerDia.getDay() + 6) % 7;

    const celdas: Array<{ dia: number | null; iso: string | null }> = [];
    for (let i = 0; i < offsetInicio; i++) {
      celdas.push({ dia: null, iso: null });
    }
    for (let d = 1; d <= totalDias; d++) {
      const iso = `${anio}-${String(mes + 1).padStart(2, "0")}-${String(
        d
      ).padStart(2, "0")}`;
      celdas.push({ dia: d, iso });
    }

    return { anioActual: anio, mesIdx: mes, celdasMes: celdas };
  }, [mesVisible]);

  const cambiarMes = (delta: number) => {
    const nueva = new Date(anioActual, mesIdx + delta, 1);
    const nuevoMesISO = `${nueva.getFullYear()}-${String(
      nueva.getMonth() + 1
    ).padStart(2, "0")}`;
    setMesVisible(nuevoMesISO);
  };

  const bloques: BloqueHorarioAgenda[] = useMemo(() => {
    if (agenda?.bloques_horarios && agenda.bloques_horarios.length > 0) {
      return agenda.bloques_horarios;
    }
    const fallback: BloqueHorarioAgenda[] = [];
    for (let h = 6; h < 23; h++) {
      const ini = `${String(h).padStart(2, "0")}:00`;
      const fin = `${String(h + 1).padStart(2, "0")}:00`;
      fallback.push({
        hora_inicio: ini,
        hora_fin: fin,
        estado: "disponible",
        conflictos: [],
        motivo: "Disponible",
      });
    }
    return fallback;
  }, [agenda]);

  // Verifica si todos los bloques entre hIni y hFin están disponibles
  const rangoSinConflicto = (hIni: string, hFin: string): boolean => {
    const enRango = bloques.filter(
      (b) => b.hora_inicio >= hIni && b.hora_fin <= hFin
    );
    if (enRango.length === 0) return false;
    return enRango.every((b) => b.estado === "disponible");
  };

  const handleClickBloque = (bloque: BloqueHorarioAgenda) => {
    if (bloque.estado !== "disponible") return;
    setAvisoRango(null);

    // Si no hay ancla previa o el usuario hace clic en un bloque anterior al ancla,
    // este bloque se convierte en el nuevo inicio (duración inicial 1h)
    if (!anclaInicio || bloque.hora_inicio < anclaInicio) {
      setAnclaInicio(bloque.hora_inicio);
      onChangeHorario(bloque.hora_inicio, bloque.hora_fin);
      return;
    }

    // Si hace clic en el mismo bloque ancla, mantenemos ese bloque de 1 hora y soltamos el ancla
    if (bloque.hora_inicio === anclaInicio) {
      setAnclaInicio(null);
      onChangeHorario(bloque.hora_inicio, bloque.hora_fin);
      return;
    }

    // Si hace clic en un bloque posterior, verificamos que no exista ningún bloque ocupado en medio
    if (rangoSinConflicto(anclaInicio, bloque.hora_fin)) {
      onChangeHorario(anclaInicio, bloque.hora_fin);
      setAnclaInicio(null);
    } else {
      // Si había un bloque ocupado en medio, iniciamos selección desde el bloque recién pulsado
      setAvisoRango(
        "El rango contenía horas ocupadas en medio; se inició la selección desde este bloque libre."
      );
      setAnclaInicio(bloque.hora_inicio);
      onChangeHorario(bloque.hora_inicio, bloque.hora_fin);
    }
  };

  const horasInicioValidas = useMemo(
    () =>
      bloques
        .filter((b) => b.estado === "disponible")
        .map((b) => b.hora_inicio),
    [bloques]
  );

  const horasFinValidas = useMemo(() => {
    const opciones: string[] = [];
    for (const b of bloques) {
      if (b.hora_fin <= horaInicio) continue;
      if (b.hora_inicio >= horaInicio && b.estado !== "disponible") {
        break; // No permitir cruzar un bloque ocupado
      }
      opciones.push(b.hora_fin);
    }
    return opciones;
  }, [bloques, horaInicio]);

  return (
    <div
      style={{
        border: "1px solid var(--color-border, #e5e7eb)",
        borderRadius: "10px",
        padding: "14px",
        backgroundColor: "var(--color-bg-elevated, #f9fafb)",
        display: "flex",
        flexDirection: "column",
        gap: "12px",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "8px",
        }}
      >
        <div>
          <strong style={{ fontSize: "14px", color: "var(--color-text)" }}>
            Calendario y Horarios Disponibles
          </strong>
          <div style={{ fontSize: "12px", color: "var(--color-text-dim)" }}>
            Selecciona un día en el calendario y haz clic en los bloques libres
            para fijar la hora de inicio y fin.
          </div>
        </div>

        {/* Leyenda visual */}
        <div
          style={{
            display: "flex",
            gap: "10px",
            fontSize: "11px",
            alignItems: "center",
            flexWrap: "wrap",
          }}
        >
          <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <span
              style={{
                width: 9,
                height: 9,
                borderRadius: "50%",
                backgroundColor: "#10b981",
                display: "inline-block",
              }}
            />
            Libre
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <span
              style={{
                width: 9,
                height: 9,
                borderRadius: "50%",
                backgroundColor: "#f59e0b",
                display: "inline-block",
              }}
            />
            Parcial
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <span
              style={{
                width: 9,
                height: 9,
                borderRadius: "50%",
                backgroundColor: "#ef4444",
                display: "inline-block",
              }}
            />
            Ocupado
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <span
              style={{
                width: 9,
                height: 9,
                borderRadius: "50%",
                backgroundColor: "#4f46e5",
                display: "inline-block",
              }}
            />
            Tu selección
          </span>
        </div>
      </div>

      {/* Layout en 2 columnas: Calendario Mensual | Bloques Horarios del Día */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(265px, 1fr))",
          gap: "14px",
          alignItems: "start",
        }}
      >
        {/* COLUMNA 1: Calendario Mensual */}
        <div
          style={{
            backgroundColor: "var(--color-surface, #ffffff)",
            border: "1px solid var(--color-border, #e5e7eb)",
            borderRadius: "8px",
            padding: "10px",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "8px",
            }}
          >
            <button
              type="button"
              onClick={() => cambiarMes(-1)}
              style={{
                border: "1px solid var(--color-border, #d1d5db)",
                background: "var(--color-bg-elevated, #f3f4f6)",
                color: "var(--color-text)",
                borderRadius: "6px",
                padding: "3px 9px",
                cursor: "pointer",
                fontWeight: 600,
              }}
              title="Mes anterior"
            >
              ◀
            </button>
            <span
              style={{
                fontWeight: 700,
                fontSize: "13.5px",
                color: "var(--color-text)",
              }}
            >
              {NOMBRES_MESES[mesIdx]} {anioActual}
            </span>
            <button
              type="button"
              onClick={() => cambiarMes(1)}
              style={{
                border: "1px solid var(--color-border, #d1d5db)",
                background: "var(--color-bg-elevated, #f3f4f6)",
                color: "var(--color-text)",
                borderRadius: "6px",
                padding: "3px 9px",
                cursor: "pointer",
                fontWeight: 600,
              }}
              title="Mes siguiente"
            >
              ▶
            </button>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(7, 1fr)",
              gap: "4px",
              textAlign: "center",
              fontSize: "11px",
              fontWeight: 600,
              color: "var(--color-text-dim, #6b7280)",
              marginBottom: "4px",
            }}
          >
            {DIAS_SEMANA.map((d) => (
              <div key={d}>{d}</div>
            ))}
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(7, 1fr)",
              gap: "4px",
            }}
          >
            {celdasMes.map((celda, idx) => {
              if (!celda.dia || !celda.iso) {
                return <div key={`empty-${idx}`} style={{ height: "34px" }} />;
              }

              const esPasado = celda.iso < hoyISO;
              const esSeleccionado = celda.iso === fechaSeleccionada;
              const infoDia = agenda?.resumen_mes?.[celda.iso];
              const estadoDia = esPasado
                ? "pasado"
                : infoDia?.estado || "libre";
              const bloqueadoDia = esPasado || estadoDia === "lleno";

              let dotColor = "#10b981"; // libre
              if (estadoDia === "parcial") dotColor = "#f59e0b";
              if (estadoDia === "lleno") dotColor = "#ef4444";
              if (estadoDia === "pasado") dotColor = "#9ca3af";

              return (
                <button
                  key={celda.iso}
                  type="button"
                  disabled={bloqueadoDia}
                  onClick={() => {
                    setAnclaInicio(null);
                    setAvisoRango(null);
                    onChangeFecha(celda.iso!);
                  }}
                  title={
                    esPasado
                      ? "Fecha transcurrida"
                      : infoDia
                        ? `${celda.iso}: ${infoDia.horas_libres}h libres, ${infoDia.horas_ocupadas}h ocupadas`
                        : celda.iso
                  }
                  style={{
                    height: "34px",
                    borderRadius: "6px",
                    border: esSeleccionado
                      ? "2px solid var(--primary, #4f46e5)"
                      : "1px solid var(--color-border, #e5e7eb)",
                    backgroundColor: esSeleccionado
                      ? "var(--primary, #4f46e5)"
                      : esPasado
                        ? "var(--color-bg-elevated, #f3f4f6)"
                        : "var(--color-surface, #ffffff)",
                    color: esSeleccionado
                      ? "#ffffff"
                      : esPasado
                        ? "var(--color-text-dim, #9ca3af)"
                        : "var(--color-text)",
                    opacity: bloqueadoDia && !esSeleccionado ? 0.5 : 1,
                    cursor: bloqueadoDia ? "not-allowed" : "pointer",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    padding: "2px 0",
                    fontSize: "12px",
                    fontWeight: esSeleccionado ? 700 : 500,
                    position: "relative",
                  }}
                >
                  <span>{celda.dia}</span>
                  <span
                    style={{
                      width: "5px",
                      height: "5px",
                      borderRadius: "50%",
                      backgroundColor: esSeleccionado ? "#ffffff" : dotColor,
                      marginTop: "2px",
                    }}
                  />
                </button>
              );
            })}
          </div>

          <div
            style={{
              marginTop: "8px",
              fontSize: "11.5px",
              color: "var(--color-text-dim)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <span>
              Fecha elegida: <strong>{fechaSeleccionada}</strong>
            </span>
            {agenda && (
              <span>
                {agenda.horas_libres_dia}h libres · {agenda.horas_ocupadas_dia}h
                ocupadas
              </span>
            )}
          </div>
        </div>

        {/* COLUMNA 2: Selector de Bloques Horarios (06:00 - 23:00) */}
        <div
          style={{
            backgroundColor: "var(--color-surface, #ffffff)",
            border: "1px solid var(--color-border, #e5e7eb)",
            borderRadius: "8px",
            padding: "10px",
            display: "flex",
            flexDirection: "column",
            gap: "8px",
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
            <span
              style={{
                fontWeight: 700,
                fontSize: "13px",
                color: "var(--color-text)",
              }}
            >
              Horarios del {fechaSeleccionada} (06:00 - 23:00)
            </span>
            <span
              style={{
                fontSize: "12px",
                fontWeight: 600,
                color: "var(--primary, #4f46e5)",
                backgroundColor: "rgba(79, 70, 229, 0.1)",
                padding: "2px 8px",
                borderRadius: "999px",
              }}
            >
              {horaInicio} - {horaFin}
            </span>
          </div>

          {anclaInicio && (
            <div
              style={{
                fontSize: "11.5px",
                color: "#1e40af",
                backgroundColor: "rgba(59, 130, 246, 0.12)",
                padding: "4px 8px",
                borderRadius: "4px",
              }}
            >
              Inicio fijado en <strong>{anclaInicio}</strong>. Haz clic en otro
              bloque libre posterior para extender la duración, o en el mismo
              bloque para 1 hora.
            </div>
          )}

          {avisoRango && (
            <div
              style={{
                fontSize: "11.5px",
                color: "#92400e",
                backgroundColor: "rgba(245, 158, 11, 0.15)",
                padding: "4px 8px",
                borderRadius: "4px",
              }}
            >
              {avisoRango}
            </div>
          )}

          {cargandoAgenda ? (
            <div
              style={{
                padding: "24px",
                textAlign: "center",
                fontSize: "12.5px",
                color: "var(--color-text-dim)",
              }}
            >
              Consultando ocupaciones del día...
            </div>
          ) : (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(92px, 1fr))",
                gap: "5px",
              }}
            >
              {bloques.map((b) => {
                const seleccionado =
                  b.hora_inicio >= horaInicio && b.hora_fin <= horaFin;
                const esOcupado = b.estado === "ocupado";
                const esPasado = b.estado === "pasado";
                const deshabilitado = esOcupado || esPasado;

                let bg = "rgba(16, 185, 129, 0.1)";
                let border = "1px solid rgba(16, 185, 129, 0.4)";
                let color = "#065f46";
                let subLabel = "Libre";

                if (seleccionado && !deshabilitado) {
                  bg = "var(--primary, #4f46e5)";
                  border = "1.5px solid var(--primary, #4f46e5)";
                  color = "#ffffff";
                  subLabel = "Seleccionado";
                } else if (esOcupado) {
                  bg = "rgba(239, 68, 68, 0.13)";
                  border = "1px solid rgba(239, 68, 68, 0.45)";
                  color = "#991b1b";
                  subLabel = "Ocupado";
                } else if (esPasado) {
                  bg = "var(--color-bg-elevated, #f3f4f6)";
                  border = "1px solid var(--color-border, #e5e7eb)";
                  color = "var(--color-text-dim, #9ca3af)";
                  subLabel = "Pasado";
                }

                return (
                  <button
                    key={b.hora_inicio}
                    type="button"
                    disabled={deshabilitado}
                    onClick={() => handleClickBloque(b)}
                    title={b.motivo}
                    style={{
                      padding: "6px 4px",
                      borderRadius: "6px",
                      backgroundColor: bg,
                      border,
                      color,
                      cursor: deshabilitado ? "not-allowed" : "pointer",
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: "11.5px",
                      lineHeight: 1.2,
                      transition: "all 0.12s ease",
                    }}
                  >
                    <strong style={{ fontSize: "11.5px" }}>
                      {b.hora_inicio} - {b.hora_fin}
                    </strong>
                    <span style={{ fontSize: "10px", opacity: 0.9 }}>
                      {subLabel}
                    </span>
                  </button>
                );
              })}
            </div>
          )}

          {/* Selectores precisos sincronizados */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "8px",
              marginTop: "4px",
              paddingTop: "8px",
              borderTop: "1px solid var(--color-border, #e5e7eb)",
            }}
          >
            <div>
              <label
                style={{
                  display: "block",
                  fontSize: "11.5px",
                  fontWeight: 600,
                  marginBottom: "2px",
                  color: "var(--color-text-dim)",
                }}
              >
                Hora Inicio
              </label>
              <select
                value={horaInicio}
                onChange={(e) => {
                  const nuevoIni = e.target.value;
                  setAnclaInicio(null);
                  const hNum = parseInt(nuevoIni.slice(0, 2), 10);
                  const sugeridoFin = `${String(Math.min(23, hNum + 1)).padStart(
                    2,
                    "0"
                  )}:00`;
                  const nuevoFin =
                    horaFin > nuevoIni && rangoSinConflicto(nuevoIni, horaFin)
                      ? horaFin
                      : sugeridoFin;
                  onChangeHorario(nuevoIni, nuevoFin);
                }}
                style={{
                  width: "100%",
                  padding: "6px 8px",
                  borderRadius: "6px",
                  border: "1px solid var(--color-border, #d1d5db)",
                  backgroundColor: "var(--color-bg-elevated, #f9fafb)",
                  color: "var(--color-text)",
                  fontSize: "13px",
                }}
              >
                {!horasInicioValidas.includes(horaInicio) && (
                  <option value={horaInicio}>{horaInicio}</option>
                )}
                {horasInicioValidas.map((h) => (
                  <option key={h} value={h}>
                    {h}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label
                style={{
                  display: "block",
                  fontSize: "11.5px",
                  fontWeight: 600,
                  marginBottom: "2px",
                  color: "var(--color-text-dim)",
                }}
              >
                Hora Fin
              </label>
              <select
                value={horaFin}
                onChange={(e) => {
                  setAnclaInicio(null);
                  onChangeHorario(horaInicio, e.target.value);
                }}
                style={{
                  width: "100%",
                  padding: "6px 8px",
                  borderRadius: "6px",
                  border: "1px solid var(--color-border, #d1d5db)",
                  backgroundColor: "var(--color-bg-elevated, #f9fafb)",
                  color: "var(--color-text)",
                  fontSize: "13px",
                }}
              >
                {!horasFinValidas.includes(horaFin) && (
                  <option value={horaFin}>{horaFin}</option>
                )}
                {horasFinValidas.map((h) => (
                  <option key={h} value={h}>
                    {h}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Detalle de ocupaciones registradas en la fecha seleccionada */}
      {agenda && agenda.ocupaciones_dia.length > 0 && (
        <div
          style={{
            backgroundColor: "var(--color-surface, #ffffff)",
            border: "1px solid var(--color-border, #e5e7eb)",
            borderRadius: "8px",
            padding: "8px 12px",
            fontSize: "12px",
          }}
        >
          <div
            style={{
              fontWeight: 700,
              marginBottom: "4px",
              color: "var(--color-text)",
            }}
          >
            Ocupaciones registradas el {fechaSeleccionada} en la(s) cancha(s)
            seleccionada(s):
          </div>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "6px",
            }}
          >
            {agenda.ocupaciones_dia.map((oc, i) => (
              <span
                key={`${oc.id_cancha}-${oc.hora_inicio}-${i}`}
                style={{
                  padding: "3px 8px",
                  borderRadius: "6px",
                  backgroundColor:
                    oc.tipo === "evento"
                      ? "rgba(79, 70, 229, 0.12)"
                      : oc.tipo === "bloqueo"
                        ? "rgba(245, 158, 11, 0.16)"
                        : "rgba(239, 68, 68, 0.12)",
                  color:
                    oc.tipo === "evento"
                      ? "#3730a3"
                      : oc.tipo === "bloqueo"
                        ? "#92400e"
                        : "#991b1b",
                  fontWeight: 500,
                }}
              >
                <strong>
                  {oc.hora_inicio} - {oc.hora_fin}
                </strong>{" "}
                · {oc.nombre_cancha} ({oc.detalle})
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default CalendarioDisponibilidadEvento;
