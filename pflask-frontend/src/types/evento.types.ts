export interface CanchaEventoDetalle {
  id_cancha: number;
  nombre_cancha: string;
  tipo_deporte?: string;
}

export interface Evento {
  id_evento: number;
  nombre_evento: string;
  tipo_evento?: string;
  fecha_evento: string; // YYYY-MM-DD
  hora_inicio: string;  // HH:MM
  hora_fin: string;     // HH:MM
  cupo_maximo?: number;
  organizador?: string;
  contacto?: string | null;
  descripcion?: string;
  id_cancha: number;
  nombre_cancha?: string;
  ids_canchas?: number[];
  nombres_canchas?: string[];
  canchas_detalle?: CanchaEventoDetalle[];
}

export interface SesionEventoDTO {
  fecha_evento: string;
  hora_inicio: string;
  hora_fin: string;
}

export interface CreateEventoDTO {
  nombre_evento: string;
  tipo_evento?: string;
  fecha_evento: string;
  hora_inicio: string;
  hora_fin: string;
  cupo_maximo?: number;
  organizador?: string;
  contacto?: string;
  descripcion?: string;
  id_cancha: number;
  ids_canchas?: number[];
  repeticiones_semanales?: number;
  sesiones_programadas?: SesionEventoDTO[];
}

export interface AlternativaHoraria {
  hora_inicio: string;
  hora_fin: string;
  direccion: "anterior" | "posterior";
  distancia_min: number;
}

export interface SesionSemanalEstado {
  numero_semana: number;
  fecha_evento: string;
  hora_inicio: string;
  hora_fin: string;
  hora_inicio_base: string;
  hora_fin_base: string;
  horario_ajustado: boolean;
  disponible: boolean;
  disponible_en_base: boolean;
  motivo?: string | null;
  motivo_base?: string | null;
  alternativas_anteriores: AlternativaHoraria[];
  alternativas_posteriores: AlternativaHoraria[];
}

export interface DisponibilidadSemanalParams {
  ids_canchas: number[];
  fecha_evento: string;
  hora_inicio: string;
  hora_fin: string;
  repeticiones_semanales: number;
  horarios_personalizados?: Record<
    string,
    { hora_inicio: string; hora_fin: string }
  >;
}

export interface DisponibilidadSemanalResponse {
  todas_disponibles: boolean;
  repeticiones_semanales: number;
  semanas_libres: number;
  semanas_con_conflicto: number;
  ids_canchas: number[];
  sesiones: SesionSemanalEstado[];
}

export interface UpdateEventoDTO extends Partial<CreateEventoDTO> {}

export interface CheckDisponibilidadParams {
  id_cancha?: number;
  ids_canchas?: number[];
  fecha_evento: string;
  hora_inicio: string;
  hora_fin: string;
  excluir_id?: number;
}

export interface DisponibilidadEventoResponse {
  disponible: boolean;
  mensaje?: string;
  motivo?: string;
  ids_canchas?: number[];
}

export interface BloqueHorarioAgenda {
  hora_inicio: string;
  hora_fin: string;
  estado: "disponible" | "ocupado" | "pasado";
  conflictos: string[];
  motivo: string;
}

export interface OcupacionDiaItem {
  hora_inicio: string;
  hora_fin: string;
  tipo: "evento" | "reserva" | "bloqueo";
  detalle: string;
  id_cancha: number;
  nombre_cancha: string;
}

export interface ResumenDiaMes {
  ocupaciones: number;
  horas_libres: number;
  horas_ocupadas: number;
  estado: "libre" | "parcial" | "lleno" | "pasado";
}

export interface AgendaDisponibilidadParams {
  ids_canchas: number[];
  fecha: string;
  mes?: string;
  excluir_id?: number;
}

export interface AgendaDisponibilidadResponse {
  fecha: string;
  mes: string;
  ids_canchas: number[];
  horas_libres_dia: number;
  horas_ocupadas_dia: number;
  bloques_horarios: BloqueHorarioAgenda[];
  ocupaciones_dia: OcupacionDiaItem[];
  resumen_mes: Record<string, ResumenDiaMes>;
}

/**
 * Construye el enlace oficial de WhatsApp (https://wa.me/numero) para solicitar
 * más información sobre un evento. Si el número tiene 8 dígitos (celular local de Bolivia),
 * antepone automáticamente el código de país 591.
 */
export function buildWhatsAppEventoUrl(evento: Evento): string | null {
  if (!evento.contacto) return null;
  const soloDigitos = evento.contacto.replace(/\D/g, "");
  if (soloDigitos.length < 7) return null;

  const numeroNormalizado =
    soloDigitos.length === 8 ? `591${soloDigitos}` : soloDigitos;

  const mensaje = `Hola, me gustaría obtener más información sobre el evento "${evento.nombre_evento}" programado para el ${evento.fecha_evento} (${evento.hora_inicio} - ${evento.hora_fin}).`;
  return `https://wa.me/${numeroNormalizado}?text=${encodeURIComponent(mensaje)}`;
}

export type EstadoTemporalEvento = "proximo" | "en_curso" | "pasado";

/**
 * Determina de forma pura si un evento está próximo, en curso o finalizado (pasado)
 * comparando su fecha y horario contra la fecha/hora local del dispositivo.
 */
export function obtenerEstadoTemporalEvento(
  evento: Pick<Evento, "fecha_evento" | "hora_inicio" | "hora_fin">
): EstadoTemporalEvento {
  const ahora = new Date();
  const hoyISO = `${ahora.getFullYear()}-${String(ahora.getMonth() + 1).padStart(2, "0")}-${String(ahora.getDate()).padStart(2, "0")}`;
  const horaActual = `${String(ahora.getHours()).padStart(2, "0")}:${String(ahora.getMinutes()).padStart(2, "0")}`;

  const fechaEv = (evento.fecha_evento || "").slice(0, 10);
  const hIni = (evento.hora_inicio || "00:00").slice(0, 5);
  const hFin = (evento.hora_fin || "23:59").slice(0, 5);

  if (fechaEv < hoyISO) {
    return "pasado";
  }
  if (fechaEv > hoyISO) {
    return "proximo";
  }
  if (hFin <= horaActual) {
    return "pasado";
  }
  if (hIni <= horaActual && horaActual < hFin) {
    return "en_curso";
  }
  return "proximo";
}
