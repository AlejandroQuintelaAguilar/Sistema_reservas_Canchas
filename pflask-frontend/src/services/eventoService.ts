import { api } from "./api";
import type {
  Evento,
  CreateEventoDTO,
  UpdateEventoDTO,
  CheckDisponibilidadParams,
  DisponibilidadEventoResponse,
  AgendaDisponibilidadParams,
  AgendaDisponibilidadResponse,
  DisponibilidadSemanalParams,
  DisponibilidadSemanalResponse,
} from "../types/evento.types";

export const eventoService = {
  getAll: async (tipo?: string): Promise<Evento[]> => {
    const response = await api.get<Evento[]>("/eventos", {
      params: tipo ? { tipo } : undefined,
    });
    return response.data;
  },

  getTipos: async (): Promise<{ valor: string; etiqueta: string }[]> => {
    const response = await api.get<{ valor: string; etiqueta: string }[]>(
      "/eventos/tipos"
    );
    return response.data;
  },

  getById: async (id: number): Promise<Evento> => {
    const response = await api.get<Evento>(`/eventos/${id}`);
    return response.data;
  },

  checkDisponibilidad: async (
    params: CheckDisponibilidadParams
  ): Promise<DisponibilidadEventoResponse> => {
    const listaCanchas =
      params.ids_canchas && params.ids_canchas.length > 0
        ? params.ids_canchas
        : params.id_cancha
          ? [params.id_cancha]
          : [];

    const query = new URLSearchParams({
      ids_canchas: listaCanchas.join(","),
      fecha_evento: params.fecha_evento,
      hora_inicio: params.hora_inicio,
      hora_fin: params.hora_fin,
    });
    if (params.excluir_id) {
      query.set("excluir_id", String(params.excluir_id));
    }
    const response = await api.get<DisponibilidadEventoResponse>(
      `/eventos/disponibilidad?${query.toString()}`
    );
    return response.data;
  },

  getAgendaDisponibilidad: async (
    params: AgendaDisponibilidadParams
  ): Promise<AgendaDisponibilidadResponse> => {
    const query = new URLSearchParams({
      ids_canchas: params.ids_canchas.join(","),
      fecha: params.fecha,
    });
    if (params.mes) {
      query.set("mes", params.mes);
    }
    if (params.excluir_id) {
      query.set("excluir_id", String(params.excluir_id));
    }
    const response = await api.get<AgendaDisponibilidadResponse>(
      `/eventos/agenda-disponibilidad?${query.toString()}`
    );
    return response.data;
  },

  checkDisponibilidadSemanal: async (
    params: DisponibilidadSemanalParams
  ): Promise<DisponibilidadSemanalResponse> => {
    const response = await api.post<DisponibilidadSemanalResponse>(
      "/eventos/disponibilidad-semanal",
      params
    );
    return response.data;
  },

  create: async (data: CreateEventoDTO): Promise<Evento> => {
    const response = await api.post<Evento>("/eventos", data);
    return response.data;
  },

  update: async (id: number, data: UpdateEventoDTO): Promise<Evento> => {
    const response = await api.put<Evento>(`/eventos/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<{ mensaje: string }> => {
    const response = await api.delete<{ mensaje: string }>(`/eventos/${id}`);
    return response.data;
  },
};
