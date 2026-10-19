/**
 * Validaciones compartidas del frontend.
 *
 * Estas reglas replican las del backend para que el usuario reciba el error en
 * el campo, no despues de un viaje al servidor:
 *   - servicios/reservas_service.py  (horario 06:00-23:00, 1-15 dias, 1-4 horas)
 *   - services/tarifas_service.py    (horario de atencion, hora_fin > hora_inicio)
 *   - validators/evento_validator.py (cupo entero, hora_fin > hora_inicio)
 *   - validators/auth_validator.py   (contrasena: 8-128, mayuscula, minuscula,
 *                                    numero y simbolo)
 *
 * La politica de contrasena esta replicada en el backend: ambas capas aplican
 * la misma regla, y aqui se usa para mostrar el error en el campo.
 */

// ---------- dominio de canchas y reservas ----------

/** Ventana de atencion; el backend la llama horario de atencion. */
export const HORA_ATENCION_MIN = "06:00";
export const HORA_ATENCION_MAX = "23:00";

export const DIAS_MIN_ANTICIPACION = 1;
export const DIAS_MAX_ANTICIPACION = 15;

export const DURACION_MIN_H = 1;
export const DURACION_MAX_H = 4;
export const DURACION_PASO_H = 0.5;

/** Tope de un monto en Bs: evita teclear 999999999 y esperar un error del servidor. */
export const MONTO_MAX = 1000000;
export const PRECIO_HORA_MAX = 100000;
export const CUPOS_MAX = 10000;

// ---------- fechas ----------

/** Fecha local en ISO (yyyy-mm-dd), sin desfase de zona horaria. */
export const fechaISO = (fecha = new Date()) => {
  const d = fecha instanceof Date ? fecha : new Date(fecha);
  const mes = String(d.getMonth() + 1).padStart(2, "0");
  const dia = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mes}-${dia}`;
};

export const hoyISO = () => fechaISO(new Date());

export const sumarDias = (dias, desde = new Date()) => {
  const d = new Date(desde);
  d.setDate(d.getDate() + dias);
  return fechaISO(d);
};

/** Limites que acepta el date-picker de reservas, para no ofrecer fechas invalidas. */
export const rangoFechaReserva = () => ({
  min: sumarDias(DIAS_MIN_ANTICIPACION),
  max: sumarDias(DIAS_MAX_ANTICIPACION),
});

/** Compara dos horas "HH:MM" como minutos desde medianoche. */
export const minutosDeHora = (hora) => {
  const [h, m] = String(hora || "").split(":").map(Number);
  if (!Number.isFinite(h) || !Number.isFinite(m)) return NaN;
  return h * 60 + m;
};

export const horaValida = (hora) => {
  const min = minutosDeHora(hora);
  return Number.isFinite(min) && hora >= HORA_ATENCION_MIN && hora <= HORA_ATENCION_MAX;
};

export const horaFinPosterior = (inicio, fin) => {
  const a = minutosDeHora(inicio);
  const b = minutosDeHora(fin);
  return Number.isFinite(a) && Number.isFinite(b) && b > a;
};

/** Minutos desde medianoche a "HH:MM"; util para armar mensajes de cierre. */
export const minutosAHora = (minutos) => {
  const h = Math.floor(minutos / 60);
  const m = minutos % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
};

/** "1:00:00" -> 1, "0:30:00" -> 0.5. Devuelve null si no se puede leer. */
export const horasDeDuracion = (duracion) => {
  if (typeof duracion === "number") return Number.isFinite(duracion) ? duracion : null;
  const partes = String(duracion || "").split(":").map(Number);
  if (!partes.length || partes.some((n) => !Number.isFinite(n))) return null;
  const [h = 0, m = 0, s = 0] = partes;
  return h + m / 60 + s / 3600;
};

/** True si las dos fechas existen y el rango no esta invertido. */
export const rangoFechasValido = (desde, hasta) => {
  if (!desde || !hasta) return false;
  return desde <= hasta;
};

/** Dias de anticipacion de una fecha; negativo si ya paso. */
export const diasDeAnticipacion = (fechaISO_texto) => {
  const hoy = new Date(`${hoyISO()}T00:00:00`);
  const objetivo = new Date(`${fechaISO_texto}T00:00:00`);
  if (Number.isNaN(objetivo.getTime())) return NaN;
  return Math.round((objetivo - hoy) / 86400000);
};

export const fechaReservaValida = (fecha) => {
  const dias = diasDeAnticipacion(fecha);
  return Number.isFinite(dias) && dias >= DIAS_MIN_ANTICIPACION && dias <= DIAS_MAX_ANTICIPACION;
};

// ---------- numeros ----------

/**
 * Convierte a numero o devuelve null. Evita que un "abc" llegue al backend como
 * NaN, que JSON.stringify convierte en null.
 */
export const aNumero = (valor) => {
  if (valor === null || valor === undefined || valor === "") return null;
  const n = Number(valor);
  return Number.isFinite(n) ? n : null;
};

export const esNumeroValido = (valor, { min, max, entero } = {}) => {
  const n = aNumero(valor);
  if (n === null) return false;
  if (entero && !Number.isInteger(n)) return false;
  if (min !== undefined && n < min) return false;
  if (max !== undefined && n > max) return false;
  return true;
};

/** Mensaje de error para un numero fuera de rango; util para setError. */
export const errorNumero = (etiqueta, { min, max, entero } = {}) => {
  const partes = [];
  if (min !== undefined) partes.push(`mínimo ${min}`);
  if (max !== undefined) partes.push(`máximo ${max}`);
  const rango = partes.length ? ` (${partes.join(", ")})` : "";
  const tipo = entero ? "un número entero" : "un número";
  return `${etiqueta} debe ser ${tipo}${rango}.`;
};

// ---------- texto ----------

/** El required de HTML acepta "" pero no "   ": esto cubre los dos casos. */
export const textoVacio = (valor) => !String(valor ?? "").trim();

export const sinEspacios = (valor, etiqueta) =>
  textoVacio(valor) ? `${etiqueta} es obligatorio.` : "";

// ---------- identificadores ----------

/** CI boliviano: solo digitos, de 4 a 10. */
export const CI_RE = /^[0-9]{4,10}$/;
/** Celular-Linea: 7 a 15 digitos, con prefijo internacional opcional. */
export const CELULAR_RE = /^\+?[0-9]{7,15}$/;
/** Usuario: 4 a 30 caracteres alfanumericos mas _ . - */
export const USERNAME_RE = /^[A-Za-z0-9._-]{4,30}$/;
export const URL_RE = /^https?:\/\/[^\s]+$/i;

/**
 * Deja unicamente digitos. Se usa en los campos numericos (CI, celular) para
 * que la letra no llegue a escribirse, en vez de avisar recien al enviar.
 */
export const soloDigitos = (valor) => String(valor ?? "").replace(/\D+/g, "");

/** Celular: solo digitos, conservando un "+" unicamente al inicio. */
export const soloDigitosCelular = (valor) => {
  const v = String(valor ?? "").replace(/^\s+/, "");
  const digitos = v.replace(/\D+/g, "");
  return v.startsWith("+") ? `+${digitos}` : digitos;
};

export const errorFormato = (valor, re, mensaje) =>
  !re.test(String(valor ?? "").trim()) ? mensaje : "";

// ---------- contrasena ----------

export const PASSWORD_MIN = 8;
export const PASSWORD_MAX = 128;

/**
 * Regla unica de contrasena del proyecto. Se aplica en registro, reset, alta
 * de cliente por parte del empleado y alta de empleados: si una pantalla la
 * cumple y otra no, la mas debil decide la seguridad de todas.
 */
export const REGLAS_PASSWORD = [
  { prueba: (v) => v.length >= PASSWORD_MIN, mensaje: `Mínimo ${PASSWORD_MIN} caracteres.` },
  { prueba: (v) => /[A-Z]/.test(v), mensaje: "Debe tener una mayúscula." },
  { prueba: (v) => /[a-z]/.test(v), mensaje: "Debe tener una minúscula." },
  { prueba: (v) => /[0-9]/.test(v), mensaje: "Debe tener un número." },
  { prueba: (v) => /[^A-Za-z0-9]/.test(v), mensaje: "Debe tener un símbolo." },
];

/** Devuelve los mensajes de las reglas incumplidas; vacio si la contrasena sirve. */
export const erroresContrasena = (valor) =>
  REGLAS_PASSWORD.filter((r) => !r.prueba(String(valor ?? ""))).map((r) => r.mensaje);

export const contrasenaValida = (valor) => {
  const v = String(valor ?? "");
  return v.length >= PASSWORD_MIN && v.length <= PASSWORD_MAX && erroresContrasena(v).length === 0;
};

/**
 * Texto listo para mostrar bajo un campo de contrasena: "Mayúscula, minúscula,
 * número, símbolo y al menos 8 caracteres."
 */
export const REQUISITOS_PASSWORD =
  "Mínimo 8 caracteres, con mayúscula, minúscula, número y símbolo.";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Valida el formulario de usuario del panel de administracion (crear y editar).
 * Devuelve "" si todo esta bien, o el primer mensaje de error.
 *
 * El backend (auth_controller.py) exige nombre, correo y contrasena al crear y
 * solo mira que la contrasena tenga 8 caracteres: el formato de CI, celular y
 * usuario no se puede atrapar en ningun otro lado.
 */
export const validarFormularioUsuario = (form, { passwordObligatoria = false } = {}) => {
  const nombre = String(form?.nombre ?? "");
  const email = String(form?.email ?? "").trim();
  const ci = String(form?.ci ?? "").trim();
  const celular = String(form?.celular ?? "").trim();
  const username = String(form?.username ?? "").trim();
  const password = String(form?.password ?? "");

  if (textoVacio(nombre)) return "El nombre es obligatorio.";
  if (textoVacio(email)) return "El correo es obligatorio.";
  if (!EMAIL_RE.test(email)) return "Debe ser un correo válido.";
  if (!textoVacio(ci) && !CI_RE.test(ci)) {
    return "El CI debe tener entre 4 y 10 dígitos, sin letras.";
  }
  if (!textoVacio(celular) && !CELULAR_RE.test(celular)) {
    return "El celular debe tener entre 7 y 15 dígitos.";
  }
  if (!textoVacio(username) && !USERNAME_RE.test(username)) {
    return "El usuario debe tener entre 4 y 30 caracteres: letras, números, punto, guion o guion bajo.";
  }
  if (passwordObligatoria || password) {
    const errores = erroresContrasena(password);
    if (errores.length) return `La contraseña no cumple la política: ${errores.join(" ")}`;
  }
  return "";
};

/**
 * Alta de cliente desde el modal del empleado (ReservasPage). A diferencia del
 * registro publico, aqui la contrasena la elige el empleado, asi que tiene que
 * cumplir la misma politica o el cliente nace con una clave debil.
 */
export const validarAltaCliente = ({
  nombre,
  apellido,
  ci,
  celular,
  email,
  username,
  password,
} = {}) => {
  if (textoVacio(nombre)) return "El nombre es obligatorio.";
  if (textoVacio(apellido)) return "El apellido es obligatorio.";
  if (textoVacio(ci)) return "El CI es obligatorio.";
  if (!CI_RE.test(String(ci).trim())) {
    return "El CI debe tener entre 4 y 10 dígitos, sin letras.";
  }
  if (!textoVacio(celular) && !CELULAR_RE.test(String(celular).trim())) {
    return "El celular debe tener entre 7 y 15 dígitos.";
  }
  if (!textoVacio(email) && !EMAIL_RE.test(String(email).trim())) {
    return "Debe ser un correo válido.";
  }
  if (textoVacio(username)) return "El nombre de usuario es obligatorio.";
  if (!USERNAME_RE.test(String(username).trim())) {
    return "El usuario debe tener entre 4 y 30 caracteres: letras, números, punto, guion o guion bajo.";
  }
  const errores = erroresContrasena(password);
  if (errores.length) return `La contraseña no cumple la política: ${errores.join(" ")}`;
  return "";
};

/**
 * Schema de yup para un campo contrasena + su confirmacion, para no repetir el
 * mismo bloque en cada formulario.
 */
export const esquemaContrasena = (yup, campo = "password", campoConfirmacion) => {
  const base = yup
    .string()
    .required("La contraseña es obligatoria.")
    .min(PASSWORD_MIN, `Mínimo ${PASSWORD_MIN} caracteres.`)
    .max(PASSWORD_MAX, `Máximo ${PASSWORD_MAX} caracteres.`)
    .matches(/[A-Z]/, "Debe tener una mayúscula.")
    .matches(/[a-z]/, "Debe tener una minúscula.")
    .matches(/[0-9]/, "Debe tener un número.")
    .matches(/[^A-Za-z0-9]/, "Debe tener un símbolo.");

  if (!campoConfirmacion) return base;
  return {
    [campo]: base,
    // required antes de oneOf: si no, el mensaje que se ve es "no coinciden"
    // en vez de "confirma la contraseña".
    [campoConfirmacion]: yup
      .string()
      .required("Confirma la contraseña.")
      .oneOf([yup.ref(campo)], "Las contraseñas no coinciden."),
  };
};