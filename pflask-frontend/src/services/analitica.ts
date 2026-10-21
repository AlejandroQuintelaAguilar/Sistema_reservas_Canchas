import { api } from "./api";

export type TipoAnalisis = "reservas" | "pagos" | "canchas" | "clientes";

export interface ParametroAnalisis {
  nombre: string;
  etiqueta: string;
  tipo: "texto" | "numero" | "fecha" | "lista" | "booleano";
  opciones?: { valor: string; etiqueta: string }[];
}

export interface TipoCatalogo {
  valor: TipoAnalisis;
  etiqueta: string;
  descripcion: string;
  parametros: ParametroAnalisis[];
}

export interface ResumenAnalisis {
  id_analisis: number;
  tipo_analisis: TipoAnalisis;
  fecha_inicio: string;
  fecha_fin: string;
  parametros: Record<string, unknown> | null;
  metricas: Record<string, unknown> | null;
  generado_en: string;
  generado_por: string | null;
  estado: "ok" | "corrupto";
  error?: string;
  total_registros: number;
}

export interface Analisis extends ResumenAnalisis {
  resultado: Record<string, unknown> | null;
}

export interface GenerarAnalisis {
  /** Opcional: el backend decide si hay datos y guarda cuando corresponde. */
  guardar?: boolean;
  tipo_analisis: TipoAnalisis;
  fecha_inicio: string;
  fecha_fin: string;
  parametros?: Record<string, unknown>;
}

export interface RespuestaGenerar {
  guardado: boolean;
  mensaje: string;
  analisis: Analisis | null;
  metricas: Record<string, unknown> | null;
  detalle: Record<string, unknown> | null;
}

export const analiticaService = {
  resumen: async () => {
    const { data } = await api.get("/analitica");
    return data as {
      reservas: Record<string, unknown>;
      pagos: Record<string, unknown>;
      canchas: Record<string, unknown>;
      clientes: Record<string, unknown>;
      ocupacion?: Record<string, unknown>;
    };
  },

  catalogos: async () => {
    const { data } = await api.get("/analitica/tipos");
    return data as { tipos: TipoCatalogo[] };
  },

  generar: async (cuerpo: GenerarAnalisis) => {
    const { data } = await api.post("/analitica/analisis", cuerpo);
    return data as RespuestaGenerar;
  },

  listar: async (filtros: {
    tipo_analisis?: string;
    desde?: string;
    hasta?: string;
    limite?: number;
  } = {}) => {
    const { data } = await api.get("/analitica/analisis", { params: filtros });
    return data as ResumenAnalisis[];
  },

  detalle: async (id: number) => {
    const { data } = await api.get(`/analitica/analisis/${id}`);
    return data as Analisis;
  },

  eliminar: async (id: number) => {
    const { data } = await api.delete(`/analitica/analisis/${id}`);
    return data;
  },

  comparar: async (
    id: number,
    fechaInicio: string,
    fechaFin: string
  ) => {
    const { data } = await api.get(`/analitica/analisis/${id}/comparar`, {
      params: { fecha_inicio: fechaInicio, fecha_fin: fechaFin },
    });
    return data as {
      comparacion: boolean;
      mensaje: string;
      diferencias: Record<string, number | null>;
      referencia: { metricas: Record<string, unknown> };
      actual: { metricas: Record<string, unknown> };
    };
  },

  /**
   * Descarga el analisis pasando el token de sesion. Un <a href> no lleva el
   * encabezado Authorization y el endpoint es privado, asi que bajaria 401.
   */
  descargar: async (id: number, formato: "pdf" | "excel") => {
    const { data } = await api.get(`/analitica/analisis/${id}/exportar`, {
      params: { formato },
      responseType: "blob",
    });
    const tipoMime =
      formato === "excel"
        ? "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        : "application/pdf";
    const url = URL.createObjectURL(new Blob([data], { type: tipoMime }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `analisis-${id}.${formato}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
};
