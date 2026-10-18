from datetime import datetime, date
from services.eventos_service import TIPOS_EVENTO_VALIDOS


class EventoValidator:
    @staticmethod
    def _validar_tipo(data, errors):
        tipo = data.get("tipo_evento")
        if tipo is None or str(tipo).strip() == "":
            errors.append("El campo 'tipo_evento' es obligatorio.")
            return
        if tipo not in TIPOS_EVENTO_VALIDOS:
            errors.append(
                f"'tipo_evento' debe ser uno de: {', '.join(TIPOS_EVENTO_VALIDOS)}."
            )

    @staticmethod
    def _validar_cupo(data, errors):
        cupo = data.get("cupo_maximo")
        if cupo is None or str(cupo).strip() == "":
            errors.append("El campo 'cupo_maximo' es obligatorio.")
            return
        try:
            if int(cupo) <= 0:
                errors.append("El cupo máximo debe ser un entero positivo.")
        except (ValueError, TypeError):
            errors.append("El cupo máximo debe ser un número entero.")

    @staticmethod
    def validate_create_payload(data):
        errors = []
        if not data:
            return False, ["No se proporcionaron datos JSON."]

        required_fields = ["nombre_evento", "fecha_evento", "hora_inicio", "hora_fin", "id_cancha"]
        for field in required_fields:
            if field not in data or data[field] is None or str(data[field]).strip() == "":
                errors.append(f"El campo '{field}' es obligatorio.")

        if errors:
            return False, errors

        EventoValidator._validar_tipo(data, errors)
        EventoValidator._validar_cupo(data, errors)

        # Validar formato de fecha (YYYY-MM-DD) y que no sea anterior a hoy
        fecha = None
        try:
            fecha = datetime.strptime(data["fecha_evento"], "%Y-%m-%d").date()
            if fecha < date.today():
                errors.append("La fecha del evento no puede ser anterior a la fecha actual.")
        except ValueError:
            errors.append("El formato de 'fecha_evento' debe ser YYYY-MM-DD.")

        # Validar horas (HH:MM) y que no hayan transcurrido hoy
        try:
            h_inicio = datetime.strptime(data["hora_inicio"], "%H:%M").time()
            h_fin = datetime.strptime(data["hora_fin"], "%H:%M").time()
            if h_fin <= h_inicio:
                errors.append("La hora de fin debe ser estrictamente posterior a la hora de inicio.")
            elif fecha == date.today() and h_inicio <= datetime.now().time():
                errors.append(
                    f"La hora de inicio ({data['hora_inicio']}) ya ha transcurrido "
                    f"para la fecha de hoy (hora actual: {datetime.now().strftime('%H:%M')})."
                )
        except ValueError:
            errors.append("Las horas deben tener formato militar HH:MM (ej. 14:30).")

        # Validar id_cancha
        try:
            int(data["id_cancha"])
        except (ValueError, TypeError):
            errors.append("El identificador 'id_cancha' debe ser un número entero.")

        if errors:
            return False, errors
        return True, []

    @staticmethod
    def validate_update_payload(data):
        errors = []
        if not data:
            return False, ["No se proporcionaron datos JSON."]

        if "nombre_evento" in data and str(data["nombre_evento"] or "").strip() == "":
            errors.append("El campo 'nombre_evento' no puede quedar vacío.")

        if "tipo_evento" in data:
            EventoValidator._validar_tipo(data, errors)

        if "cupo_maximo" in data:
            EventoValidator._validar_cupo(data, errors)

        fecha = None
        if "fecha_evento" in data and data["fecha_evento"]:
            try:
                fecha = datetime.strptime(data["fecha_evento"], "%Y-%m-%d").date()
                if fecha < date.today():
                    errors.append("La fecha del evento no puede ser anterior a la fecha actual.")
            except ValueError:
                errors.append("El formato de 'fecha_evento' debe ser YYYY-MM-DD.")

        for campo in ("hora_inicio", "hora_fin"):
            if campo in data and data[campo]:
                try:
                    datetime.strptime(data[campo], "%H:%M")
                except ValueError:
                    errors.append(f"'{campo}' debe tener formato militar HH:MM (ej. 14:30).")

        if data.get("hora_inicio") and data.get("hora_fin"):
            try:
                h_inicio = datetime.strptime(data["hora_inicio"], "%H:%M").time()
                h_fin = datetime.strptime(data["hora_fin"], "%H:%M").time()
                if h_fin <= h_inicio:
                    errors.append("La hora de fin debe ser estrictamente posterior a la hora de inicio.")
                elif fecha == date.today() and h_inicio <= datetime.now().time():
                    errors.append(
                        f"La hora de inicio ({data['hora_inicio']}) ya ha transcurrido "
                        f"para la fecha de hoy (hora actual: {datetime.now().strftime('%H:%M')})."
                    )
            except ValueError:
                pass

        if "id_cancha" in data and data["id_cancha"] is not None:
            try:
                int(data["id_cancha"])
            except (ValueError, TypeError):
                errors.append("El identificador 'id_cancha' debe ser un número entero.")

        if errors:
            return False, errors
        return True, []
