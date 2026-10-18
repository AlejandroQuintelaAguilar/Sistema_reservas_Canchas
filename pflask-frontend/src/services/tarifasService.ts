import { api } from "./api";

export interface Tarifa {
  id_tarifa: number;
  id_cancha: number;
  tipo_tarifa: TipoTarifa;
  dia_semana: number | null;
  dia_nombre: string;
  hora_inicio: string;
  hora_fin: string;
  precio_hora: number;
  activo: boolean;
  fecha: string;
}

export type TipoTarifa = "normal" | "nocturna" | "fin_semana";

export interface HorarioDia {
  id_horario: number | null;
  id_cancha: number;
  dia_semana: number;
  dia_nombre: string;
  hora_apertura: string | null;
  hora_cierre: string | null;
  activo: boolean;
  por_defecto: boolean;
}

export interface TarifaDTO {
  id_cancha: number;
  tipo_tarifa: TipoTarifa;
  dia_semana: number | null;
  hora_inicio: string;
  hora_fin: string;
  precio_hora: number;
}

export interface HistorialTarifa {
  id_historial: number;
  id_cancha: number;
  accion: string;
  tipo_anterior: string | null;
  tipo_nuevo: string | null;
  dia_anterior: number | null;
  dia_anterior_nombre: string | null;
  dia_nuevo: number | null;
  dia_nuevo_nombre: string | null;
  precio_anterior: number | null;
  precio_nuevo: number | null;
  motivo: string | null;
  fecha: string;
}

export const DIAS = [
  "Lunes",
  "Martes",
  "Miércoles",
  "Jueves",
  "Viernes",
  "Sábado",
  "Domingo",
];

export const ETIQUETA_TIPO: Record<TipoTarifa, string> = {
  normal: "Normal",
  nocturna: "Nocturna",
  fin_semana: "Fin de semana",
};

/** Franjas sugeridas al abrir el formulario de nueva tarifa. */
export const FRANJAS_SUGERIDAS: Record<TipoTarifa, [string, string]> = {
  normal: ["06:00", "18:00"],
  nocturna: ["18:00", "23:00"],
  fin_semana: ["06:00", "23:00"],
};

const mensajeError = (e: unknown, porDefecto: string): string => {
  const err = e as { response?: { data?: { mensaje?: string; error?: string; detalle?: string } } };
  const data = err?.response?.data;
  return data?.detalle || data?.mensaje || data?.error || porDefecto;
};

export const tarifasService = {
  async listarCancha(idCancha: number, incluirInactivas = true): Promise<Tarifa[]> {
    try {
      const { data } = await api.get<Tarifa[]>(
        `/canchas/${idCancha}/tarifas?todas=${incluirInactivas}`,
      );
      return data;
    } catch (e) {
      throw new Error(mensajeError(e, "No se pudieron cargar las tarifas."));
    }
  },

  async listarHorarios(idCancha: number): Promise<HorarioDia[]> {
    try {
      const { data } = await api.get<HorarioDia[]>(`/canchas/${idCancha}/horarios`);
      return data;
    } catch (e) {
      throw new Error(mensajeError(e, "No se pudieron cargar los horarios."));
    }
  },

  async guardarHorarios(
    idCancha: number,
    horarios: Array<Pick<HorarioDia, "dia_semana" | "hora_apertura" | "hora_cierre" | "activo">>,
  ): Promise<HorarioDia[]> {
    try {
      const { data } = await api.put<HorarioDia[]>(
        `/admin/canchas/${idCancha}/horarios`,
        { horarios },
      );
      return data;
    } catch (e) {
      throw new Error(mensajeError(e, "No se pudieron guardar los horarios."));
    }
  },

  async crear(datos: TarifaDTO): Promise<Tarifa> {
    try {
      const { data } = await api.post<Tarifa>("/admin/tarifas", datos);
      return data;
    } catch (e) {
      throw new Error(mensajeError(e, "No se pudo crear la tarifa."));
    }
  },

  async actualizar(idTarifa: number, datos: Partial<TarifaDTO> & { activo?: boolean }): Promise<Tarifa> {
    try {
      const { data } = await api.put<Tarifa>(`/admin/tarifas/${idTarifa}`, datos);
      return data;
    } catch (e) {
      throw new Error(mensajeError(e, "No se pudo actualizar la tarifa."));
    }
  },

  async eliminar(idTarifa: number): Promise<void> {
    try {
      await api.delete(`/admin/tarifas/${idTarifa}`);
    } catch (e) {
      throw new Error(mensajeError(e, "No se pudo eliminar la tarifa."));
    }
  },

  async eliminarTodas(idCancha: number): Promise<void> {
    try {
      await api.delete(`/admin/canchas/${idCancha}/tarifas`);
    } catch (e) {
      throw new Error(mensajeError(e, "No se pudieron eliminar las tarifas."));
    }
  },

  async historial(idCancha: number): Promise<HistorialTarifa[]> {
    try {
      const { data } = await api.get<HistorialTarifa[]>(
        `/admin/canchas/${idCancha}/tarifas/historial`,
      );
      return data;
    } catch (e) {
      throw new Error(mensajeError(e, "No se pudo cargar el historial."));
    }
  },
};
