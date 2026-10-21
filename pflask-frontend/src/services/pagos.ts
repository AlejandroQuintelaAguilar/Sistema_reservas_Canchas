import axiosClient from "../api/axiosClient";

/** Estados reales del modulo de Pagos. */
export type EstadoPago =
  | "pendiente"
  | "pendiente_validacion"
  | "aprobado"
  | "rechazado"
  | "expirado"
  | "devuelto";

export type MetodoPago = "efectivo" | "qr" | "transferencia" | "tarjeta";

export interface Pago {
  id_pago: number;
  metodo_pago: string;
  estado_pago: EstadoPago;
  estado_label: string;
  monto: number | null;
  monto_devuelto: number;
  saldo_restante: number;
  fecha_pago: string | null;
  fecha_validacion: string | null;
  fecha_devolucion: string | null;
  referencia: string | null;
  comprobante: string | null;
  sha256: string | null;
  nombre_original: string | null;
  content_type: string | null;
  tamano_bytes: number | null;
  motivo_rechazo: string | null;
  motivo_devolucion: string | null;
  id_reserva: number;
  id_empleado: number | null;
  id_usuario: number | null;
  id_usuario_validador: number | null;
  /** Solo llega con detalle=1 */
  saldo_reserva?: number;
  solicitudes_devolucion?: DevolucionSolicitud[];
  reserva?: {
    id_reserva: number;
    fecha_reserva: string | null;
    hora_inicio: string | null;
    estado_reserva: string;
    monto_total: number;
    cancha: string | null;
    cliente: string | null;
  };
}

export interface EstadoPagoCatalogo {
  valor: EstadoPago;
  etiqueta: string;
}

export interface ReservaParaPago {
  id_reserva: number;
  fecha_reserva: string | null;
  hora_inicio: string | null;
  monto_total: number | null;
  /** Saldo que falta por cubrir; 0 significa reserva ya pagada. */
  saldo_pendiente: number;
  estado_reserva: string;
  cancha: string;
  tipo_deporte: string;
  cliente: string;
}

export interface DevolucionSolicitud {
  id_solicitud: number;
  id_pago: number;
  id_cliente: number | null;
  monto: number | null;
  motivo: string;
  estado: "solicitada" | "aprobada" | "rechazada";
  motivo_decision: string | null;
  monto_devuelto: number | null;
  fecha_devolucion: string | null;
  fecha_solicitud: string | null;
  fecha_decision: string | null;
  id_usuario_solicitante: number | null;
  id_usuario_decision: number | null;
  pago?: Pago;
}

export interface TurnoCaja {
  id_turno: number;
  id_empleado: number;
  empleado: string | null;
  fecha: string | null;
  hora_apertura: string | null;
  hora_cierre: string | null;
  monto_esperado_efectivo: number;
  monto_fisico: number | null;
  diferencia: number | null;
  total_qr: number;
  total_transferencia: number;
  total_tarjeta: number;
  total_digital: number;
  cantidad_pagos: number;
  cantidad_devoluciones: number;
  estado: "abierto" | "cerrado";
  observaciones: string | null;
  id_usuario_cierre: number | null;
}

export interface Arqueo extends Partial<TurnoCaja> {
  id_turno: number;
  monto_esperado_efectivo: number;
  total_devuelto_efectivo: number;
  cantidad_devoluciones: number;
  pagos: Pago[];
}

export interface PagoAuditoria {
  id_auditoria: number;
  id_pago: number;
  resultado: string;
  monto_comprobante: number | null;
  fecha_comprobante: string | null;
  metodo_comprobante: string | null;
  referencia_comprobante: string | null;
  observaciones: string | null;
  fecha: string | null;
  id_usuario: number | null;
}

export interface RespPago {
  mensaje: string;
  pago: Pago;
  saldo_reserva: number;
  estado_reserva: string;
  /** Presente cuando la operacion llego por el canal idempotente. */
  duplicado?: boolean;
}

export const pagosService = {
  listar: async (params: { estado?: string; detalle?: boolean; id_cliente?: number; id_reserva?: number } = {}) => {
    const { data } = await axiosClient.get<Pago[]>("/api/pagos", {
      params: {
        estado: params.estado || undefined,
        detalle: params.detalle ? "1" : undefined,
        id_cliente: params.id_cliente || undefined,
        id_reserva: params.id_reserva || undefined,
      },
    });
    return data;
  },

  estados: async () => {
    const { data } = await axiosClient.get<{ estados: EstadoPagoCatalogo[] }>("/api/pagos/estados");
    return data.estados;
  },

  obtener: async (id: number) => {
    const { data } = await axiosClient.get<Pago>(`/api/pagos/${id}`);
    return data;
  },

  saldoReserva: async (idReserva: number) => {
    const { data } = await axiosClient.get<{ id_reserva: number; saldo: number }>(
      `/api/pagos/saldo/${idReserva}`,
    );
    return data.saldo;
  },

  listarReservasParaPago: async () => {
    const { data } = await axiosClient.get<ReservaParaPago[]>("/api/pagos/reservas-para-pago");
    return data;
  },

  /** Efectivo en ventanilla: el empleado/admin registra y queda aprobado. */
  registrarEfectivo: async (datos: {
    id_reserva: number;
    monto: number;
    id_empleado?: number;
    id_turno?: number;
    referencia?: string;
  }) => {
    const { data } = await axiosClient.post<RespPago>("/api/pagos", {
      ...datos,
      metodo_pago: "efectivo",
    });
    return data;
  },

  /** Pago digital sin archivo: queda pendiente y el cliente adjunta despues. */
  registrarDigital: async (datos: {
    id_reserva: number;
    metodo_pago: MetodoPago;
    monto: number;
    referencia?: string;
  }) => {
    const { data } = await axiosClient.post<RespPago>("/api/pagos", datos);
    return data;
  },

  /** Crea el pago y sube el comprobante en la misma peticion (multipart). */
  registrarConComprobante: async (datos: {
    id_reserva: number;
    metodo_pago: MetodoPago;
    monto: number;
    referencia?: string;
  }, archivo: File) => {
    const form = new FormData();
    form.append("id_reserva", String(datos.id_reserva));
    form.append("metodo_pago", datos.metodo_pago);
    form.append("monto", String(datos.monto));
    if (datos.referencia) form.append("referencia", datos.referencia);
    form.append("comprobante", archivo);
    const { data } = await axiosClient.post<RespPago>("/api/pagos/comprobante", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
  },

  adjuntarComprobante: async (idPago: number, archivo: File) => {
    const form = new FormData();
    form.append("comprobante", archivo);
    const { data } = await axiosClient.post<RespPago>(`/api/pagos/${idPago}/comprobante`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
  },

  aprobar: async (idPago: number, observacion?: string) => {
    const { data } = await axiosClient.post<RespPago>(`/api/pagos/${idPago}/aprobar`, {
      observacion,
    });
    return data;
  },

  rechazar: async (idPago: number, motivo: string) => {
    const { data } = await axiosClient.post<RespPago>(`/api/pagos/${idPago}/rechazar`, { motivo });
    return data;
  },

  solicitarDevolucion: async (idPago: number, motivo: string, monto?: number) => {
    const { data } = await axiosClient.post<{ mensaje: string; solicitud: DevolucionSolicitud }>(
      `/api/pagos/${idPago}/devolucion`,
      { motivo, monto },
    );
    return data;
  },

  listarDevoluciones: async (params: { estado?: string; id_pago?: number } = {}) => {
    const { data } = await axiosClient.get<DevolucionSolicitud[]>("/api/pagos/devoluciones", {
      params: {
        estado: params.estado || undefined,
        id_pago: params.id_pago || undefined,
      },
    });
    return data;
  },

  aprobarDevolucion: async (idSolicitud: number) => {
    const { data } = await axiosClient.post<{ mensaje: string; solicitud: DevolucionSolicitud }>(
      `/api/pagos/devoluciones/${idSolicitud}/aprobar`,
    );
    return data;
  },

  rechazarDevolucion: async (idSolicitud: number, motivo: string) => {
    const { data } = await axiosClient.post<{ mensaje: string; solicitud: DevolucionSolicitud }>(
      `/api/pagos/devoluciones/${idSolicitud}/rechazar`,
      { motivo },
    );
    return data;
  },

  auditar: async (idPago: number, datos: {
    monto_comprobante?: number;
    fecha_comprobante?: string;
    metodo_comprobante?: string;
    referencia_comprobante?: string;
  }) => {
    const { data } = await axiosClient.post<{ mensaje: string; auditoria: PagoAuditoria }>(
      `/api/pagos/${idPago}/auditar`,
      datos,
    );
    return data;
  },

  listarAuditorias: async () => {
    const { data } = await axiosClient.get<PagoAuditoria[]>("/api/pagos/auditorias/listado");
    return data;
  },

  /**
   * Descarga el recibo PDF. Va por axios y no como <a href> porque el
   * endpoint exige el token de sesion.
   */
  descargarRecibo: async (idPago: number) => {
    const { data } = await axiosClient.get(`/api/pagos/${idPago}/recibo`, {
      responseType: "blob",
    });
    const url = URL.createObjectURL(new Blob([data], { type: "application/pdf" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `recibo-pago-${idPago}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },

  /** Devuelve una URL temporal para previsualizar el comprobante adjunto. */
  verComprobante: async (idPago: number): Promise<string> => {
    const { data } = await axiosClient.get(`/api/pagos/${idPago}/comprobante`, {
      responseType: "blob",
    });
    return URL.createObjectURL(new Blob([data]));
  },
};

export const cajaService = {
  abrirTurno: async (idEmpleado?: number) => {
    const { data } = await axiosClient.post<TurnoCaja>("/api/caja/turnos", {
      id_empleado: idEmpleado,
    });
    return data;
  },

  listarTurnos: async (fecha?: string) => {
    const { data } = await axiosClient.get<TurnoCaja[]>("/api/caja/turnos", {
      params: { fecha: fecha || undefined },
    });
    return data;
  },

  /**
   * Turno abierto del usuario. El administrador puede no ser empleado, y en ese
   * caso el backend responde 400 con un mensaje claro en vez de un 500.
   */
  turnoActual: async (): Promise<Partial<TurnoCaja>> => {
    try {
      const { data } = await axiosClient.get<Partial<TurnoCaja>>("/api/caja/actual");
      return data;
    } catch (e: any) {
      if (e.response?.status === 400) return {};
      throw e;
    }
  },

  arqueo: async (idTurno: number) => {
    const { data } = await axiosClient.get<Arqueo>(`/api/caja/turnos/${idTurno}/arqueo`);
    return data;
  },

  cerrarTurno: async (idTurno: number, montoFisico: number, observaciones?: string) => {
    const { data } = await axiosClient.post<TurnoCaja>(`/api/caja/turnos/${idTurno}/cerrar`, {
      monto_fisico: montoFisico,
      observaciones,
    });
    return data;
  },
};
