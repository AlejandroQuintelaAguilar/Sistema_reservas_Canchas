import { api } from "./api";

export type EstadoNotificacion = "pendiente" | "enviado" | "fallido";

export interface Plantilla {
  id_plantilla: number;
  codigo: string;
  nombre: string;
  tipo_evento: string;
  canal: "email" | "sms" | "push";
  asunto: string;
  cuerpo: string;
  activa: boolean;
  fecha_creacion: string | null;
}

export interface Intento {
  id_intento: number;
  numero_intento: number;
  canal: string;
  estado: string;
  detalle: string | null;
  fecha: string | null;
}

export interface Notificacion {
  id_notificacion: number;
  id_plantilla: number | null;
  id_reserva: number | null;
  id_administrador: number | null;
  tipo: string;
  canal: "email" | "sms" | "push";
  destinatario: string;
  asunto: string;
  cuerpo: string;
  estado: EstadoNotificacion;
  intentos: number;
  max_intentos: number;
  fecha_programada: string | null;
  fecha_envio: string | null;
  ultimo_error: string | null;
  clave_idempotencia: string | null;
  fecha_creacion: string | null;
  historial?: Intento[];
}

export const notificacionesService = {
  listarPlantillas: async (incluirInactivas = false): Promise<Plantilla[]> => {
    const { data } = await api.get<Plantilla[]>("/notificaciones/plantillas", {
      params: incluirInactivas ? { incluir_inactivas: "1" } : undefined,
    });
    return data;
  },

  crearPlantilla: async (datos: Partial<Plantilla>): Promise<Plantilla> => {
    const { data } = await api.post<Plantilla>("/notificaciones/plantillas", datos);
    return data;
  },

  actualizarPlantilla: async (
    id: number,
    datos: Partial<Plantilla>
  ): Promise<Plantilla> => {
    const { data } = await api.put<Plantilla>(`/notificaciones/plantillas/${id}`, datos);
    return data;
  },

  eliminarPlantilla: async (id: number) => {
    const { data } = await api.delete(`/notificaciones/plantillas/${id}`);
    return data;
  },

  listar: async (
    estado?: EstadoNotificacion,
    tipo?: string,
    idReserva?: number
  ): Promise<Notificacion[]> => {
    const { data } = await api.get<Notificacion[]>("/notificaciones", {
      params: {
        ...(estado ? { estado } : {}),
        ...(tipo ? { tipo } : {}),
        ...(idReserva ? { id_reserva: idReserva } : {}),
      },
    });
    return data;
  },

  detalle: async (id: number): Promise<Notificacion> => {
    const { data } = await api.get<Notificacion>(`/notificaciones/${id}`);
    return data;
  },

  reintentar: async (id: number) => {
    const { data } = await api.post(`/notificaciones/${id}/reintentar`);
    return data;
  },

  enviarPendientes: async () => {
    const { data } = await api.post("/notificaciones/enviar-pendientes");
    return data.resultado as {
      enviadas: number;
      fallidas: number;
      omitidas: number;
    };
  },

  generarRecordatorios: async () => {
    const { data } = await api.post("/notificaciones/generar-recordatorios");
    return data.creadas as number;
  },
};
