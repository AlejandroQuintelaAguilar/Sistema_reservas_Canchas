import { api } from "./api";
import type { Evento, CreateEventoDTO, UpdateEventoDTO } from "../types/evento.types";

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
