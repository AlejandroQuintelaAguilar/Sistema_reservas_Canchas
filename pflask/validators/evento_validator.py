import re
from datetime import datetime, date, time

HORA_APERTURA_COMPLEJO = time(6, 0)
HORA_CIERRE_COMPLEJO = time(23, 0)
PATRON_CONTACTO = re.compile(r"^\+?[\d\s\-()]{7,20}$")


class EventoValidator:
    """
    Validador de payloads para el módulo de Eventos (SRP).
    Valida exclusivamente estructura, tipos de datos, formatos y reglas de dominio
    de entrada sin acoplar consultas a la base de datos.
    """

    @staticmethod
    def _parse_hora(valor, nombre_campo):
        try:
            return datetime.strptime(str(valor).strip(), "%H:%M").time(), None
        except (ValueError, TypeError):
            return None, f"El campo '{nombre_campo}' debe tener formato militar HH:MM (ej. 14:30)."

    @staticmethod
    def _validar_rango_operativo(h_inicio, h_fin):
        errores = []
        if h_inicio and h_inicio < HORA_APERTURA_COMPLEJO:
            errores.append(
                f"La hora de inicio debe ser a partir de las {HORA_APERTURA_COMPLEJO.strftime('%H:%M')}."
            )
        if h_fin and h_fin > HORA_CIERRE_COMPLEJO:
            errores.append(
                f"La hora de fin no puede exceder el horario de cierre ({HORA_CIERRE_COMPLEJO.strftime('%H:%M')})."
            )
        return errores

    @staticmethod
    def _validar_contacto(valor):
        if valor is None or str(valor).strip() == "":
            return []
        texto = str(valor).strip()
        solo_digitos = re.sub(r"\D", "", texto)
        if not PATRON_CONTACTO.match(texto) or len(solo_digitos) < 7 or len(solo_digitos) > 15:
            return [
                "El campo 'contacto' debe ser un número de teléfono o WhatsApp válido (de 7 a 15 dígitos)."
            ]
        return []

    @staticmethod
    def _validar_canchas_payload(data, obligatorio=True):
        raw_list = data.get("ids_canchas")
        raw_single = data.get("id_cancha")

        if raw_list is not None:
            if not isinstance(raw_list, list) or len(raw_list) == 0:
                return ["Debe seleccionar al menos una cancha para el evento."]
            errores = []
            for item in raw_list:
                try:
                    cid = int(item)
                    if cid <= 0:
                        errores.append("Todos los identificadores en 'ids_canchas' deben ser enteros positivos.")
                        break
                except (ValueError, TypeError):
                    errores.append("Todos los identificadores en 'ids_canchas' deben ser números enteros.")
                    break
            return errores

        if raw_single is not None and str(raw_single).strip() != "":
            try:
                cid = int(raw_single)
                if cid <= 0:
                    return ["El identificador 'id_cancha' debe ser un entero positivo."]
                return []
            except (ValueError, TypeError):
                return ["El identificador 'id_cancha' debe ser un número entero."]

        if obligatorio:
            return ["Debe seleccionar al menos una cancha ('id_cancha' o 'ids_canchas')."]
        return []

    @staticmethod
    def validate_create_payload(data):
        errors = []
        if not data or not isinstance(data, dict):
            return False, ["No se proporcionaron datos JSON válidos."]

        required_fields = ["nombre_evento", "fecha_evento", "hora_inicio", "hora_fin"]
        for field in required_fields:
            if field not in data or data[field] is None or str(data[field]).strip() == "":
                errors.append(f"El campo '{field}' es obligatorio.")

        cancha_errors = EventoValidator._validar_canchas_payload(data, obligatorio=True)
        errors.extend(cancha_errors)

        if errors:
            return False, errors

        # Validar formato de fecha (YYYY-MM-DD) y que no sea anterior a hoy
        fecha = None
        try:
            fecha = datetime.strptime(str(data["fecha_evento"]).strip(), "%Y-%m-%d").date()
            if fecha < date.today():
                errors.append("La fecha del evento no puede ser anterior a la fecha actual.")
        except (ValueError, TypeError):
            errors.append("El formato de 'fecha_evento' debe ser YYYY-MM-DD.")

        # Validar horas (HH:MM), rango operativo y que no hayan transcurrido hoy
        h_inicio, err_ini = EventoValidator._parse_hora(data["hora_inicio"], "hora_inicio")
        h_fin, err_fin = EventoValidator._parse_hora(data["hora_fin"], "hora_fin")

        if err_ini or err_fin:
            errors.append("Las horas deben tener formato militar HH:MM (ej. 14:30).")
        else:
            if h_fin <= h_inicio:
                errors.append("La hora de fin debe ser estrictamente posterior a la hora de inicio.")
            else:
                errors.extend(EventoValidator._validar_rango_operativo(h_inicio, h_fin))
                if fecha == date.today() and h_inicio <= datetime.now().time():
                    h_actual = datetime.now().strftime("%H:%M")
                    errors.append(
                        f"La hora de inicio ({data['hora_inicio']}) ya ha transcurrido para la fecha de hoy (hora actual: {h_actual})."
                    )

        # Validar cupo
        if "cupo_maximo" in data and data["cupo_maximo"] not in (None, ""):
            try:
                cupo = int(data["cupo_maximo"])
                if cupo <= 0:
                    errors.append("El cupo máximo debe ser un entero positivo.")
            except (ValueError, TypeError):
                errors.append("El cupo máximo debe ser un número entero.")

        # Validar contacto opcional
        if "contacto" in data:
            errors.extend(EventoValidator._validar_contacto(data.get("contacto")))

        if errors:
            return False, errors
        return True, []

    @staticmethod
    def validate_update_payload(data):
        errors = []
        if not data or not isinstance(data, dict):
            return False, ["No se proporcionaron datos JSON válidos."]

        if "nombre_evento" in data and (data["nombre_evento"] is None or str(data["nombre_evento"]).strip() == ""):
            errors.append("El campo 'nombre_evento' no puede estar vacío.")

        if "fecha_evento" in data and data["fecha_evento"] not in (None, ""):
            try:
                fecha = datetime.strptime(str(data["fecha_evento"]).strip(), "%Y-%m-%d").date()
                if fecha < date.today():
                    errors.append("La fecha del evento no puede ser anterior a la fecha actual.")
            except (ValueError, TypeError):
                errors.append("El formato de 'fecha_evento' debe ser YYYY-MM-DD.")

        h_inicio = None
        h_fin = None
        if "hora_inicio" in data and data["hora_inicio"] not in (None, ""):
            h_inicio, err_ini = EventoValidator._parse_hora(data["hora_inicio"], "hora_inicio")
            if err_ini:
                errors.append(err_ini)

        if "hora_fin" in data and data["hora_fin"] not in (None, ""):
            h_fin, err_fin = EventoValidator._parse_hora(data["hora_fin"], "hora_fin")
            if err_fin:
                errors.append(err_fin)

        if h_inicio and h_fin and h_fin <= h_inicio:
            errors.append("La hora de fin debe ser estrictamente posterior a la hora de inicio.")

        errors.extend(EventoValidator._validar_rango_operativo(h_inicio, h_fin))

        if "cupo_maximo" in data and data["cupo_maximo"] not in (None, ""):
            try:
                cupo = int(data["cupo_maximo"])
                if cupo <= 0:
                    errors.append("El cupo máximo debe ser un entero positivo.")
            except (ValueError, TypeError):
                errors.append("El cupo máximo debe ser un número entero.")

        if "contacto" in data:
            errors.extend(EventoValidator._validar_contacto(data.get("contacto")))

        if "ids_canchas" in data or "id_cancha" in data:
            errors.extend(EventoValidator._validar_canchas_payload(data, obligatorio=False))

        if errors:
            return False, errors
        return True, []
