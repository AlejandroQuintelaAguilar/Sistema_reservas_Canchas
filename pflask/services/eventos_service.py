import calendar
from datetime import datetime, date, time, timedelta
from sqlalchemy import text, or_
from extensions import db
from models.cancha import Cancha
from models.evento import Evento, evento_cancha

HORA_APERTURA_COMPLEJO = time(6, 0)
HORA_CIERRE_COMPLEJO = time(23, 0)


class EventosService:
    _tabla_verificada = False

    @classmethod
    def _asegurar_tabla_evento_cancha(cls):
        if cls._tabla_verificada:
            return
        try:
            with db.session.begin_nested():
                db.session.execute(
                    text("""
                        CREATE TABLE IF NOT EXISTS public.evento_cancha (
                            id_evento INTEGER NOT NULL
                                REFERENCES public.evento(id_evento) ON DELETE CASCADE ON UPDATE CASCADE,
                            id_cancha INTEGER NOT NULL
                                REFERENCES public.cancha(id_cancha) ON DELETE RESTRICT ON UPDATE CASCADE,
                            PRIMARY KEY (id_evento, id_cancha)
                        );
                        ALTER TABLE public.evento
                            ADD COLUMN IF NOT EXISTS contacto VARCHAR(30);
                    """)
                )
            cls._tabla_verificada = True
        except Exception:
            pass

    @staticmethod
    def _extraer_lista_canchas(valor_canchas):
        """
        Convierte un entero, string separado por comas o lista en una lista única de IDs de cancha.
        """
        if valor_canchas is None:
            return []
        if isinstance(valor_canchas, (int, float)):
            return [int(valor_canchas)]
        if isinstance(valor_canchas, str):
            partes = [p.strip() for p in valor_canchas.split(",") if p.strip()]
            ids = []
            for p in partes:
                cid = int(p)
                if cid not in ids:
                    ids.append(cid)
            return ids
        if isinstance(valor_canchas, (list, tuple, set)):
            ids = []
            for item in valor_canchas:
                if item is None or str(item).strip() == "":
                    continue
                cid = int(item)
                if cid not in ids:
                    ids.append(cid)
            return ids
        return []

    @classmethod
    def get_all_eventos(cls):
        cls._asegurar_tabla_evento_cancha()
        return Evento.query.order_by(Evento.fecha_evento.asc(), Evento.hora_inicio.asc()).all()

    @classmethod
    def get_evento_by_id(cls, id_evento):
        cls._asegurar_tabla_evento_cancha()
        return db.session.get(Evento, id_evento)

    @classmethod
    def _verificar_disponibilidad(
        cls,
        ids_canchas,
        fecha,
        hora_inicio,
        hora_fin,
        id_evento_excluir=None,
        validar_hora_pasada=True,
    ):
        """
        Verifica de forma atómica que una o más canchas se encuentren operativas y libres
        durante todo el intervalo solicitado:
        - Comprueba fecha/hora válida y horario operativo (06:00 - 23:00).
        - Para cada cancha seleccionada:
          1. Comprueba que exista y no esté 'fuera_servicio' ni en 'mantenimiento'.
          2. Comprueba solapamientos con otros eventos (tanto en evento.id_cancha como en evento_cancha).
          3. Comprueba solapamientos con reservas activas en la tabla 'reserva'.
          4. Comprueba solapamientos con bloqueos activos en la tabla 'bloqueo'.
        """
        cls._asegurar_tabla_evento_cancha()
        lista_canchas = cls._extraer_lista_canchas(ids_canchas)
        if not lista_canchas:
            raise ValueError("Debe seleccionar al menos una cancha para el evento.")

        if isinstance(fecha, str):
            fecha = datetime.strptime(fecha.strip(), "%Y-%m-%d").date()
        if isinstance(hora_inicio, str):
            hora_inicio = datetime.strptime(hora_inicio.strip(), "%H:%M").time()
        if isinstance(hora_fin, str):
            hora_fin = datetime.strptime(hora_fin.strip(), "%H:%M").time()

        if hora_fin <= hora_inicio:
            raise ValueError("La hora de fin debe ser posterior a la hora de inicio.")

        if hora_inicio < HORA_APERTURA_COMPLEJO or hora_fin > HORA_CIERRE_COMPLEJO:
            raise ValueError(
                f"El horario del evento debe estar dentro del horario del complejo ({HORA_APERTURA_COMPLEJO.strftime('%H:%M')} - {HORA_CIERRE_COMPLEJO.strftime('%H:%M')})."
            )

        ahora = datetime.now()
        if validar_hora_pasada:
            if fecha < ahora.date():
                raise ValueError("No se pueden programar eventos en una fecha anterior a la actual.")
            if fecha == ahora.date() and hora_inicio <= ahora.time():
                h_actual = ahora.strftime("%H:%M")
                raise ValueError(
                    f"No se pueden programar eventos en una hora que ya ha transcurrido (hora actual: {h_actual})."
                )

        for id_cancha in lista_canchas:
            # 0. Comprobar existencia y estado operativo de la cancha
            cancha_data = db.session.execute(
                text("SELECT nombre_cancha, estado FROM cancha WHERE id_cancha = :cancha"),
                {"cancha": id_cancha},
            ).fetchone()

            if not cancha_data:
                raise ValueError(f"La cancha seleccionada (ID {id_cancha}) no existe.")

            nombre_cancha, estado_cancha = cancha_data[0], cancha_data[1]
            if estado_cancha == "fuera_servicio":
                raise ValueError(
                    f"La cancha '{nombre_cancha}' se encuentra fuera de servicio y no puede recibir eventos."
                )
            if estado_cancha == "mantenimiento":
                raise ValueError(
                    f"La cancha '{nombre_cancha}' se encuentra en mantenimiento y no puede recibir eventos."
                )

            # 1. Comprobar choque con otros eventos (en cancha principal o en tabla puente evento_cancha)
            query_eventos = (
                Evento.query.outerjoin(
                    evento_cancha, Evento.id_evento == evento_cancha.c.id_evento
                )
                .filter(
                    or_(
                        Evento.id_cancha == id_cancha,
                        evento_cancha.c.id_cancha == id_cancha,
                    ),
                    Evento.fecha_evento == fecha,
                    Evento.hora_inicio < hora_fin,
                    Evento.hora_fin > hora_inicio,
                )
            )
            if id_evento_excluir:
                query_eventos = query_eventos.filter(Evento.id_evento != id_evento_excluir)

            evento_solapado = query_eventos.first()
            if evento_solapado:
                h_ini = evento_solapado.hora_inicio.strftime("%H:%M")
                h_fin = evento_solapado.hora_fin.strftime("%H:%M")
                raise ValueError(
                    f"Conflicto en '{nombre_cancha}': Ya tiene asignado el evento '{evento_solapado.nombre_evento}' ({h_ini} - {h_fin})."
                )

            # 2. Consulta de solo lectura sobre la tabla reserva
            reserva_choque = db.session.execute(
                text("""
                    SELECT id_reserva, hora_inicio, hora_fin 
                    FROM reserva 
                    WHERE id_cancha = :cancha 
                      AND fecha_reserva = :fecha 
                      AND LOWER(estado_reserva) NOT IN ('cancelada', 'expirada')
                      AND (hora_inicio < :fin AND hora_fin > :inicio)
                    LIMIT 1
                """),
                {
                    "cancha": id_cancha,
                    "fecha": fecha,
                    "inicio": hora_inicio,
                    "fin": hora_fin,
                },
            ).fetchone()

            if reserva_choque:
                r_ini = str(reserva_choque[1])[:5]
                r_fin = str(reserva_choque[2])[:5]
                raise ValueError(
                    f"Conflicto en '{nombre_cancha}': Cuenta con una reserva activa en ese horario ({r_ini} - {r_fin})."
                )

            # 3. Consulta de solo lectura sobre la tabla bloqueo
            bloqueo_choque = None
            try:
                with db.session.begin_nested():
                    bloqueo_choque = db.session.execute(
                        text("""
                            SELECT id_bloqueo, hora_inicio, hora_fin, motivo
                            FROM bloqueo
                            WHERE id_cancha = :cancha
                              AND LOWER(estado) = 'activo'
                              AND fecha_inicio <= :fecha
                              AND fecha_fin >= :fecha
                              AND (hora_inicio < :fin AND hora_fin > :inicio)
                            LIMIT 1
                        """),
                        {
                            "cancha": id_cancha,
                            "fecha": fecha,
                            "inicio": hora_inicio,
                            "fin": hora_fin,
                        },
                    ).fetchone()
            except Exception:
                bloqueo_choque = None

            if bloqueo_choque:
                b_ini = str(bloqueo_choque[1])[:5]
                b_fin = str(bloqueo_choque[2])[:5]
                motivo = bloqueo_choque[3] or "Mantenimiento programado"
                raise ValueError(
                    f"Conflicto en '{nombre_cancha}': Tiene un bloqueo activo en ese horario ({b_ini} - {b_fin}: {motivo})."
                )

    @classmethod
    def verificar_disponibilidad_cancha(
        cls,
        ids_canchas,
        fecha_str,
        hora_inicio_str,
        hora_fin_str,
        id_evento_excluir=None,
    ):
        """
        Verifica de forma preventiva si una o varias canchas están libres para reservar un evento.
        """
        try:
            lista_canchas = cls._extraer_lista_canchas(ids_canchas)
            if not lista_canchas:
                return {
                    "disponible": False,
                    "motivo": "Selecciona al menos una cancha para verificar disponibilidad.",
                }

            excluir_int = int(id_evento_excluir) if id_evento_excluir else None
            validar_hora_pasada = True

            if excluir_int:
                ev_actual = db.session.get(Evento, excluir_int)
                if ev_actual:
                    f_req = datetime.strptime(str(fecha_str).strip(), "%Y-%m-%d").date()
                    hi_req = datetime.strptime(str(hora_inicio_str).strip(), "%H:%M").time()
                    if f_req == ev_actual.fecha_evento and hi_req == ev_actual.hora_inicio:
                        validar_hora_pasada = False

            cls._verificar_disponibilidad(
                ids_canchas=lista_canchas,
                fecha=fecha_str,
                hora_inicio=hora_inicio_str,
                hora_fin=hora_fin_str,
                id_evento_excluir=excluir_int,
                validar_hora_pasada=validar_hora_pasada,
            )
            msg = (
                f"Las {len(lista_canchas)} canchas seleccionadas están disponibles en este horario."
                if len(lista_canchas) > 1
                else "Cancha disponible para reservar el evento en este horario."
            )
            return {
                "disponible": True,
                "mensaje": msg,
                "ids_canchas": lista_canchas,
            }
        except ValueError as ve:
            return {
                "disponible": False,
                "motivo": str(ve),
            }
        except Exception:
            return {
                "disponible": False,
                "motivo": "Parámetros de fecha, hora o canchas inválidos.",
            }

    @classmethod
    def obtener_agenda_ocupacion(
        cls,
        ids_canchas,
        fecha_str,
        mes_str=None,
        id_evento_excluir=None,
    ):
        """
        Obtiene la agenda completa de disponibilidad y ocupaciones (eventos, reservas y bloqueos)
        para las canchas seleccionadas en una fecha y mes determinados, alimentando el calendario
        interactivo y la grilla de bloques horarios (06:00 a 23:00).
        """
        cls._asegurar_tabla_evento_cancha()
        lista_canchas = cls._extraer_lista_canchas(ids_canchas)
        if not lista_canchas:
            raise ValueError("Debe proporcionar al menos una cancha.")

        fecha_sel = datetime.strptime(str(fecha_str).strip(), "%Y-%m-%d").date()
        if mes_str and len(str(mes_str).strip()) >= 7:
            partes_mes = str(mes_str).strip()[:7].split("-")
            anio_mes, mes_num = int(partes_mes[0]), int(partes_mes[1])
        else:
            anio_mes, mes_num = fecha_sel.year, fecha_sel.month

        _, ultimo_dia_num = calendar.monthrange(anio_mes, mes_num)
        inicio_mes = date(anio_mes, mes_num, 1)
        fin_mes = date(anio_mes, mes_num, ultimo_dia_num)

        # Incluir también la fecha seleccionada por si pertenece a otro mes distinto al visible
        rango_inicio = min(inicio_mes, fecha_sel)
        rango_fin = max(fin_mes, fecha_sel)

        excluir_int = int(id_evento_excluir) if id_evento_excluir else None

        # Mapa de canchas seleccionadas
        canchas_objs = Cancha.query.filter(Cancha.id_cancha.in_(lista_canchas)).all()
        mapa_canchas = {c.id_cancha: c.nombre_cancha for c in canchas_objs}
        canchas_no_operativas = {
            c.id_cancha: c.estado
            for c in canchas_objs
            if c.estado in ("fuera_servicio", "mantenimiento")
        }

        # Estructura de ocupaciones por fecha: { date: [ {hora_inicio, hora_fin, tipo, detalle, id_cancha, nombre_cancha} ] }
        ocupaciones_por_fecha = {}

        def _agregar_ocupacion(f_item, h_ini, h_fin, tipo, detalle, cid):
            if isinstance(h_ini, str):
                h_ini = datetime.strptime(h_ini[:5], "%H:%M").time()
            if isinstance(h_fin, str):
                h_fin = datetime.strptime(h_fin[:5], "%H:%M").time()
            ocup_list = ocupaciones_por_fecha.setdefault(f_item, [])
            ocup_list.append({
                "hora_inicio": h_ini,
                "hora_fin": h_fin,
                "hora_inicio_str": h_ini.strftime("%H:%M"),
                "hora_fin_str": h_fin.strftime("%H:%M"),
                "tipo": tipo,
                "detalle": detalle,
                "id_cancha": cid,
                "nombre_cancha": mapa_canchas.get(cid, f"Cancha #{cid}"),
            })

        # 1. Consultar eventos en el rango para las canchas seleccionadas
        query_ev = (
            Evento.query.outerjoin(
                evento_cancha, Evento.id_evento == evento_cancha.c.id_evento
            )
            .filter(
                or_(
                    Evento.id_cancha.in_(lista_canchas),
                    evento_cancha.c.id_cancha.in_(lista_canchas),
                ),
                Evento.fecha_evento >= rango_inicio,
                Evento.fecha_evento <= rango_fin,
            )
        )
        if excluir_int:
            query_ev = query_ev.filter(Evento.id_evento != excluir_int)

        for ev in query_ev.all():
            canchas_ev = [c.id_cancha for c in ev.obtener_canchas_ordenadas()] or [ev.id_cancha]
            for cid in canchas_ev:
                if cid in lista_canchas:
                    _agregar_ocupacion(
                        ev.fecha_evento,
                        ev.hora_inicio,
                        ev.hora_fin,
                        "evento",
                        f"Evento: {ev.nombre_evento}",
                        cid,
                    )

        # 2. Consultar reservas activas en el rango
        for cid in lista_canchas:
            filas_res = db.session.execute(
                text("""
                    SELECT id_reserva, fecha_reserva, hora_inicio, hora_fin, estado_reserva
                    FROM reserva
                    WHERE id_cancha = :cid
                      AND fecha_reserva >= :ini
                      AND fecha_reserva <= :fin
                      AND LOWER(estado_reserva) NOT IN ('cancelada', 'expirada')
                """),
                {"cid": cid, "ini": rango_inicio, "fin": rango_fin},
            ).fetchall()
            for r in filas_res:
                _agregar_ocupacion(
                    r[1],
                    r[2],
                    r[3],
                    "reserva",
                    f"Reserva #{r[0]} ({r[4]})",
                    cid,
                )

        # 3. Consultar bloqueos activos en el rango
        try:
            with db.session.begin_nested():
                for cid in lista_canchas:
                    filas_bloq = db.session.execute(
                        text("""
                            SELECT id_bloqueo, fecha_inicio, fecha_fin, hora_inicio, hora_fin, motivo
                            FROM bloqueo
                            WHERE id_cancha = :cid
                              AND LOWER(estado) = 'activo'
                              AND fecha_fin >= :ini
                              AND fecha_inicio <= :fin
                        """),
                        {"cid": cid, "ini": rango_inicio, "fin": rango_fin},
                    ).fetchall()
                    for b in filas_bloq:
                        f_cur = max(b[1], rango_inicio)
                        f_top = min(b[2], rango_fin)
                        while f_cur <= f_top:
                            _agregar_ocupacion(
                                f_cur,
                                b[3],
                                b[4],
                                "bloqueo",
                                f"Bloqueo: {b[5] or 'Mantenimiento'}",
                                cid,
                            )
                            f_cur += timedelta(days=1)
        except Exception:
            pass

        ahora = datetime.now()
        hoy = ahora.date()
        hora_actual = ahora.time()

        def _evaluar_bloques_dia(fecha_eval):
            lista_oc = ocupaciones_por_fecha.get(fecha_eval, [])
            bloques = []
            horas_libres = 0
            horas_ocupadas = 0

            for h in range(6, 23):
                b_ini = time(h, 0)
                b_fin = time(h + 1, 0)
                b_ini_str = b_ini.strftime("%H:%M")
                b_fin_str = b_fin.strftime("%H:%M")

                if canchas_no_operativas:
                    cid_malo, est_malo = next(iter(canchas_no_operativas.items()))
                    nom_malo = mapa_canchas.get(cid_malo, f"Cancha #{cid_malo}")
                    bloques.append({
                        "hora_inicio": b_ini_str,
                        "hora_fin": b_fin_str,
                        "estado": "ocupado",
                        "conflictos": [f"{nom_malo} está en estado '{est_malo}'"],
                        "motivo": f"{nom_malo} no está operativa ({est_malo})",
                    })
                    horas_ocupadas += 1
                    continue

                conflictos = []
                for oc in lista_oc:
                    if oc["hora_inicio"] < b_fin and oc["hora_fin"] > b_ini:
                        etiqueta = f"{oc['nombre_cancha']}: {oc['detalle']} ({oc['hora_inicio_str']}-{oc['hora_fin_str']})"
                        if etiqueta not in conflictos:
                            conflictos.append(etiqueta)

                if conflictos:
                    estado_b = "ocupado"
                    motivo_b = " · ".join(conflictos)
                    horas_ocupadas += 1
                elif fecha_eval < hoy or (fecha_eval == hoy and b_ini <= hora_actual):
                    estado_b = "pasado"
                    motivo_b = "Horario ya transcurrido"
                else:
                    estado_b = "disponible"
                    motivo_b = "Disponible"
                    horas_libres += 1

                bloques.append({
                    "hora_inicio": b_ini_str,
                    "hora_fin": b_fin_str,
                    "estado": estado_b,
                    "conflictos": conflictos,
                    "motivo": motivo_b,
                })

            return bloques, horas_libres, horas_ocupadas

        # Construir resumen de todos los días del mes consultado
        resumen_mes = {}
        dia_cursor = inicio_mes
        while dia_cursor <= fin_mes:
            iso_d = dia_cursor.isoformat()
            if dia_cursor < hoy:
                resumen_mes[iso_d] = {
                    "ocupaciones": len(ocupaciones_por_fecha.get(dia_cursor, [])),
                    "horas_libres": 0,
                    "horas_ocupadas": 0,
                    "estado": "pasado",
                }
            else:
                _, h_lib, h_oc = _evaluar_bloques_dia(dia_cursor)
                if h_lib == 0:
                    est_dia = "lleno"
                elif h_oc > 0:
                    est_dia = "parcial"
                else:
                    est_dia = "libre"
                resumen_mes[iso_d] = {
                    "ocupaciones": len(ocupaciones_por_fecha.get(dia_cursor, [])),
                    "horas_libres": h_lib,
                    "horas_ocupadas": h_oc,
                    "estado": est_dia,
                }
            dia_cursor += timedelta(days=1)

        # Construir detalle del día seleccionado
        bloques_dia_sel, libres_sel, ocupadas_sel = _evaluar_bloques_dia(fecha_sel)
        ocupaciones_dia_sel = sorted(
            [
                {
                    "hora_inicio": oc["hora_inicio_str"],
                    "hora_fin": oc["hora_fin_str"],
                    "tipo": oc["tipo"],
                    "detalle": oc["detalle"],
                    "id_cancha": oc["id_cancha"],
                    "nombre_cancha": oc["nombre_cancha"],
                }
                for oc in ocupaciones_por_fecha.get(fecha_sel, [])
            ],
            key=lambda x: (x["hora_inicio"], x["id_cancha"]),
        )

        return {
            "fecha": fecha_sel.isoformat(),
            "mes": f"{anio_mes:04d}-{mes_num:02d}",
            "ids_canchas": lista_canchas,
            "horas_libres_dia": libres_sel,
            "horas_ocupadas_dia": ocupadas_sel,
            "bloques_horarios": bloques_dia_sel,
            "ocupaciones_dia": ocupaciones_dia_sel,
            "resumen_mes": resumen_mes,
        }

    @classmethod
    def create_evento(cls, data):
        cls._asegurar_tabla_evento_cancha()
        fecha = datetime.strptime(str(data["fecha_evento"]).strip(), "%Y-%m-%d").date()
        if fecha < date.today():
            raise ValueError("La fecha del evento no puede ser anterior a la fecha actual.")

        inicio = datetime.strptime(str(data["hora_inicio"]).strip(), "%H:%M").time()
        fin = datetime.strptime(str(data["hora_fin"]).strip(), "%H:%M").time()

        if fin <= inicio:
            raise ValueError("La hora de fin debe ser posterior a la hora de inicio.")

        ids_canchas = cls._extraer_lista_canchas(
            data.get("ids_canchas") if data.get("ids_canchas") is not None else data.get("id_cancha")
        )
        if not ids_canchas:
            raise ValueError("Debe seleccionar al menos una cancha para el evento.")

        cupo_maximo = (
            int(data["cupo_maximo"])
            if data.get("cupo_maximo") not in (None, "")
            else None
        )

        # Verificar disponibilidad atómica de todas las canchas seleccionadas
        cls._verificar_disponibilidad(ids_canchas, fecha, inicio, fin)

        canchas_objs = Cancha.query.filter(Cancha.id_cancha.in_(ids_canchas)).all()

        nuevo_evento = Evento(
            nombre_evento=str(data["nombre_evento"]).strip(),
            tipo_evento=str(data["tipo_evento"]).strip() if data.get("tipo_evento") else None,
            fecha_evento=fecha,
            hora_inicio=inicio,
            hora_fin=fin,
            cupo_maximo=cupo_maximo,
            organizador=str(data["organizador"]).strip() if data.get("organizador") else None,
            contacto=str(data["contacto"]).strip() if data.get("contacto") else None,
            descripcion=str(data["descripcion"]).strip() if data.get("descripcion") else None,
            id_cancha=ids_canchas[0],
            canchas=canchas_objs,
        )

        db.session.add(nuevo_evento)
        db.session.commit()
        return nuevo_evento

    @classmethod
    def update_evento(cls, id_evento, data):
        cls._asegurar_tabla_evento_cancha()
        evento = db.session.get(Evento, id_evento)
        if not evento:
            return None

        nueva_fecha = evento.fecha_evento
        nuevo_inicio = evento.hora_inicio
        nuevo_fin = evento.hora_fin
        canchas_actuales = [c.id_cancha for c in evento.obtener_canchas_ordenadas()] or [evento.id_cancha]
        nuevas_canchas = list(canchas_actuales)

        tiempo_o_cancha_cambio = False
        inicio_o_fecha_cambio = False

        if "fecha_evento" in data and data["fecha_evento"]:
            f = datetime.strptime(str(data["fecha_evento"]).strip(), "%Y-%m-%d").date()
            if f != evento.fecha_evento:
                if f < date.today():
                    raise ValueError("La fecha del evento no puede ser anterior a la fecha actual.")
                nueva_fecha = f
                tiempo_o_cancha_cambio = True
                inicio_o_fecha_cambio = True

        if "hora_inicio" in data and data["hora_inicio"]:
            hi = datetime.strptime(str(data["hora_inicio"]).strip(), "%H:%M").time()
            if hi != evento.hora_inicio:
                nuevo_inicio = hi
                tiempo_o_cancha_cambio = True
                inicio_o_fecha_cambio = True

        if "hora_fin" in data and data["hora_fin"]:
            hf = datetime.strptime(str(data["hora_fin"]).strip(), "%H:%M").time()
            if hf != evento.hora_fin:
                nuevo_fin = hf
                tiempo_o_cancha_cambio = True

        if "ids_canchas" in data and data["ids_canchas"] is not None:
            cand = cls._extraer_lista_canchas(data["ids_canchas"])
            if not cand:
                raise ValueError("Debe seleccionar al menos una cancha para el evento.")
            if set(cand) != set(canchas_actuales) or cand[0] != evento.id_cancha:
                nuevas_canchas = cand
                tiempo_o_cancha_cambio = True
        elif "id_cancha" in data and data["id_cancha"]:
            c = int(data["id_cancha"])
            if [c] != canchas_actuales:
                nuevas_canchas = [c]
                tiempo_o_cancha_cambio = True

        if nuevo_fin <= nuevo_inicio:
            raise ValueError("La hora de fin debe ser posterior a la hora de inicio.")

        # Revalidar disponibilidad si cambiaron canchas, fecha u horario
        if tiempo_o_cancha_cambio:
            cls._verificar_disponibilidad(
                nuevas_canchas,
                nueva_fecha,
                nuevo_inicio,
                nuevo_fin,
                id_evento_excluir=id_evento,
                validar_hora_pasada=inicio_o_fecha_cambio,
            )

        # Aplicar actualizaciones
        if "nombre_evento" in data and data["nombre_evento"] is not None:
            evento.nombre_evento = str(data["nombre_evento"]).strip()
        if "tipo_evento" in data:
            evento.tipo_evento = str(data["tipo_evento"]).strip() if data["tipo_evento"] else None
        evento.fecha_evento = nueva_fecha
        evento.hora_inicio = nuevo_inicio
        evento.hora_fin = nuevo_fin
        evento.id_cancha = nuevas_canchas[0]
        evento.canchas = Cancha.query.filter(Cancha.id_cancha.in_(nuevas_canchas)).all()

        if "cupo_maximo" in data:
            evento.cupo_maximo = (
                int(data["cupo_maximo"]) if data["cupo_maximo"] not in (None, "") else None
            )
        if "organizador" in data:
            evento.organizador = str(data["organizador"]).strip() if data["organizador"] else None
        if "contacto" in data:
            evento.contacto = str(data["contacto"]).strip() if data["contacto"] else None
        if "descripcion" in data:
            evento.descripcion = str(data["descripcion"]).strip() if data["descripcion"] else None

        db.session.commit()
        return evento

    @classmethod
    def delete_evento(cls, id_evento):
        """
        Elimina físicamente un evento de la base de datos y libera los horarios de sus canchas.
        """
        cls._asegurar_tabla_evento_cancha()
        evento = db.session.get(Evento, id_evento)
        if not evento:
            return False
        db.session.delete(evento)
        db.session.commit()
        return True
