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
