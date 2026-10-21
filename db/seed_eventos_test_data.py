"""
Script idempotente para sembrar datos de prueba orientados a validar
el módulo de Eventos y Servicios Sociales (multi-cancha, calendario interactivo,
contacto de WhatsApp, estados de canchas y bloqueos).
"""
import sys
from datetime import date, time
from pathlib import Path
import sqlalchemy as sa

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pflask"))

DB_URL = "postgresql://postgres:123456@localhost:5432/proyectoCanchas"


def seed():
    engine = sa.create_engine(DB_URL)

    with engine.begin() as conn:
        print("Iniciando sembrado de datos de prueba...")

        # 1. Asegurar tabla evento_cancha y columna contacto en evento
        conn.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS public.evento_cancha (
                id_evento INTEGER NOT NULL
                    REFERENCES public.evento(id_evento) ON DELETE CASCADE ON UPDATE CASCADE,
                id_cancha INTEGER NOT NULL
                    REFERENCES public.cancha(id_cancha) ON DELETE RESTRICT ON UPDATE CASCADE,
                PRIMARY KEY (id_evento, id_cancha)
            );
            ALTER TABLE public.evento ADD COLUMN IF NOT EXISTS contacto VARCHAR(30);
        """))

        # 2. Canchas adicionales con distintos estados
        canchas_data = [
            {
                "id_cancha": 604,
                "nombre_cancha": "Cancha C - Sintético Fútbol 7",
                "tipo_deporte": "Fútbol 7",
                "precio_hora": 130.00,
                "ubicacion": "Sector Norte - Campo Abierto",
                "estado": "disponible",
                "techada": False,
                "superficie": "Césped Sintético Monofilamento",
                "id_categoria": 10,
                "id_administrador": 301,
            },
            {
                "id_cancha": 605,
                "nombre_cancha": "Pista 2 - Tenis Polvo de Ladrillo",
                "tipo_deporte": "Tenis",
                "precio_hora": 90.00,
                "ubicacion": "Sector Oriente - Pistas",
                "estado": "mantenimiento",
                "techada": False,
                "superficie": "Polvo de Ladrillo",
                "id_categoria": 30,
                "id_administrador": 301,
            },
            {
                "id_cancha": 606,
                "nombre_cancha": "Cancha D - Futsal Clásico",
                "tipo_deporte": "Futsal",
                "precio_hora": 110.00,
                "ubicacion": "Pabellón Cubierto B",
                "estado": "fuera_servicio",
                "techada": True,
                "superficie": "Piso Poliuretano",
                "id_categoria": 20,
                "id_administrador": 301,
            },
        ]

        for c in canchas_data:
            existe = conn.execute(
                sa.text("SELECT id_cancha FROM cancha WHERE id_cancha = :id_cancha"),
                {"id_cancha": c["id_cancha"]},
            ).fetchone()
            if not existe:
                conn.execute(
                    sa.text("""
                        INSERT INTO cancha (
                            id_cancha, nombre_cancha, tipo_deporte, precio_hora,
                            ubicacion, estado, techada, superficie, id_categoria, id_administrador
                        ) VALUES (
                            :id_cancha, :nombre_cancha, :tipo_deporte, :precio_hora,
                            :ubicacion, :estado, :techada, :superficie, :id_categoria, :id_administrador
                        )
                    """),
                    c,
                )
                print(f"  [+] Cancha agregada: {c['nombre_cancha']} ({c['estado']})")
            else:
                print(f"  [.] Cancha ya existente: {c['nombre_cancha']}")

        # 3. Bloqueo de mantenimiento en Cancha 602
        bloqueo_data = {
            "id_bloqueo": 901,
            "fecha_inicio": date(2026, 10, 28),
            "fecha_fin": date(2026, 10, 28),
            "hora_inicio": time(8, 0),
            "hora_fin": time(12, 0),
            "motivo": "Mantenimiento y repintado de demarcaciones",
            "estado": "activo",
            "id_cancha": 602,
            "id_administrador": 301,
        }
        existe_bloq = conn.execute(
            sa.text("SELECT id_bloqueo FROM bloqueo WHERE id_bloqueo = :id_bloqueo"),
            {"id_bloqueo": bloqueo_data["id_bloqueo"]},
        ).fetchone()
        if not existe_bloq:
            conn.execute(
                sa.text("""
                    INSERT INTO bloqueo (
                        id_bloqueo, fecha_inicio, fecha_fin, hora_inicio, hora_fin,
                        motivo, estado, id_cancha, id_administrador
                    ) VALUES (
                        :id_bloqueo, :fecha_inicio, :fecha_fin, :hora_inicio, :hora_fin,
                        :motivo, :estado, :id_cancha, :id_administrador
                    )
                """),
                bloqueo_data,
            )
            print(f"  [+] Bloqueo registrado: {bloqueo_data['motivo']} en cancha #{bloqueo_data['id_cancha']}")
        else:
            print(f"  [.] Bloqueo ya existente: #{bloqueo_data['id_bloqueo']}")

        # 4. Eventos de prueba
        eventos_data = [
            {
                "id_evento": 702,
                "nombre_evento": "Taller Comunitario de Iniciación al Fútbol Infantil",
                "tipo_evento": "Servicio Social",
                "fecha_evento": date(2026, 10, 29),
                "hora_inicio": time(10, 0),
                "hora_fin": time(12, 0),
                "cupo_maximo": 35,
                "organizador": "Fundación Deporte y Vida",
                "contacto": "+59171234567",
                "descripcion": "Taller formativo gratuito para niños de 6 a 12 años del barrio.",
                "id_cancha": 601,
                "ids_canchas": [601, 604],
            },
            {
                "id_evento": 703,
                "nombre_evento": "Torneo Relámpago de Pádel Nocturno",
                "tipo_evento": "Deportivo",
                "fecha_evento": date(2026, 10, 31),
                "hora_inicio": time(17, 0),
                "hora_fin": time(21, 0),
                "cupo_maximo": 16,
                "organizador": "Club Pádel Pro",
                "contacto": "72345678",
                "descripcion": "Competencia rápida por parejas en modalidad todos contra todos.",
                "id_cancha": 603,
                "ids_canchas": [603],
            },
            {
                "id_evento": 704,
                "nombre_evento": "Jornada de Integración Vecinal y Voluntariado",
                "tipo_evento": "Servicio Social",
                "fecha_evento": date(2026, 11, 5),
                "hora_inicio": time(14, 0),
                "hora_fin": time(18, 0),
                "cupo_maximo": 50,
                "organizador": "Junta Vecinal Central",
                "contacto": None,
                "descripcion": "Actividades recreativas y deportivas organizadas por los vecinos de la zona.",
                "id_cancha": 602,
                "ids_canchas": [602],
            },
        ]

        for ev in eventos_data:
            existe_ev = conn.execute(
                sa.text("SELECT id_evento FROM evento WHERE id_evento = :id_evento"),
                {"id_evento": ev["id_evento"]},
            ).fetchone()
            if not existe_ev:
                conn.execute(
                    sa.text("""
                        INSERT INTO evento (
                            id_evento, nombre_evento, tipo_evento, fecha_evento,
                            hora_inicio, hora_fin, cupo_maximo, organizador,
                            contacto, descripcion, id_cancha
                        ) VALUES (
                            :id_evento, :nombre_evento, :tipo_evento, :fecha_evento,
                            :hora_inicio, :hora_fin, :cupo_maximo, :organizador,
                            :contacto, :descripcion, :id_cancha
                        )
                    """),
                    {k: ev[k] for k in ev if k != "ids_canchas"},
                )
                print(f"  [+] Evento insertado: {ev['nombre_evento']}")

            # Sincronizar tabla puente evento_cancha
            for cid in ev["ids_canchas"]:
                existe_rel = conn.execute(
                    sa.text("""
                        SELECT 1 FROM evento_cancha
                        WHERE id_evento = :id_evento AND id_cancha = :id_cancha
                    """),
                    {"id_evento": ev["id_evento"], "id_cancha": cid},
                ).fetchone()
                if not existe_rel:
                    conn.execute(
                        sa.text("""
                            INSERT INTO evento_cancha (id_evento, id_cancha)
                            VALUES (:id_evento, :id_cancha)
                        """),
                        {"id_evento": ev["id_evento"], "id_cancha": cid},
                    )
                    print(f"      -> Asignada cancha #{cid} al evento #{ev['id_evento']}")

        # Sincronizar el evento preexistente 701 a evento_cancha si no está
        existe_701_rel = conn.execute(
            sa.text("SELECT 1 FROM evento_cancha WHERE id_evento = 701 AND id_cancha = 601")
        ).fetchone()
        if not existe_701_rel:
            conn.execute(
                sa.text("INSERT INTO evento_cancha (id_evento, id_cancha) VALUES (701, 601)")
            )
            print("  [+] Sincronizada cancha #601 para el evento preexistente #701")

        # Ajustar secuencias si aplica
        conn.execute(sa.text("""
            SELECT setval(pg_get_serial_sequence('cancha', 'id_cancha'), COALESCE(MAX(id_cancha), 1)) FROM cancha;
            SELECT setval(pg_get_serial_sequence('evento', 'id_evento'), COALESCE(MAX(id_evento), 1)) FROM evento;
        """))

        print("\n¡Datos de prueba sembrados exitosamente!")


if __name__ == "__main__":
    seed()
