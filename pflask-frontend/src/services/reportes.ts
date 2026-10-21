import { api } from "./api";

export interface FiltrosReporte {
  id_cancha?: string;
  id_cliente?: string;
  estado?: string;
}

export const reportesService = {
  obtener: async (
    tipo: string,
    fechaInicio: string,
    fechaFin: string,
    filtros: FiltrosReporte = {}
  ) => {
    const { data } = await api.get(`/reportes/datos/${tipo}`, {
      params: { fecha_inicio: fechaInicio, fecha_fin: fechaFin, ...filtros },
    });
    return data;
  },

  catalogos: async () => {
    const { data } = await api.get("/reportes/tipos");
    return data as {
      tipos: string[];
      estados: { valor: string; etiqueta: string }[];
    };
  },

  listar: async () => {
    const { data } = await api.get("/reportes");
    return data;
  },

  eliminar: async (id: number) => {
    const { data } = await api.delete(`/reportes/${id}`);
    return data;
  },

  urlExportar: (
    tipo: string,
    fechaInicio: string,
    fechaFin: string,
    formato: "pdf" | "excel",
    filtros: FiltrosReporte = {}
  ) => {
    const params = new URLSearchParams({
      fecha_inicio: fechaInicio,
      fecha_fin: fechaFin,
      formato,
    });
    Object.entries(filtros).forEach(([k, v]) => {
      if (v) params.append(k, String(v));
    });
    return `/api/reportes/exportar/${tipo}?${params.toString()}`;
  },

  /**
   * Descarga el reporte pasando el token de sesion. Un <a href> no lleva el
   * encabezado Authorization y el endpoint es privado, asi que bajaria 401.
   */
  descargar: async (
    tipo: string,
    fechaInicio: string,
    fechaFin: string,
    formato: "pdf" | "excel",
    filtros: FiltrosReporte = {}
  ) => {
    const { data } = await api.get(`/reportes/exportar/${tipo}`, {
      params: { fecha_inicio: fechaInicio, fecha_fin: fechaFin, formato, ...filtros },
      responseType: "blob",
    });
    const tipoMime =
      formato === "excel"
        ? "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        : "application/pdf";
    const url = URL.createObjectURL(new Blob([data], { type: tipoMime }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `reporte-${tipo}-${fechaInicio}-${fechaFin}.${formato}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
};
