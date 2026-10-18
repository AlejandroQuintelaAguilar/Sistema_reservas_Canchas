import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";

interface Cancha {
  id: number;
  nombre: string;
  deporte: string;
  precio_hora: number;
  techada: boolean;
  estado: string;
  imagen_url?: string;
}

function CanchasPage() {
  const [canchas, setCanchas] = useState<Cancha[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get<Cancha[]>("/canchas")
      .then((res: { data: Cancha[] }) => setCanchas(res.data))
      .catch(() => setError("No se pudo conectar con el backend. ¿Está corriendo Flask?"))
      .finally(() => setCargando(false));
  }, []);

  if (cargando) return <p style={{ padding: "20px" }}>Cargando canchas...</p>;
  if (error) return <p style={{ color: "red", padding: "20px" }}>{error}</p>;

  return (
    <div style={{ padding: "20px" }}>
      <h1>Canchas disponibles</h1>
      <ul style={{ listStyleType: "none", padding: 0 }}>
        {canchas.map((c) => (
          <li key={c.id} style={{ marginBottom: "15px", padding: "10px", border: "1px solid #ccc", borderRadius: "5px" }}>
            {c.imagen_url ? (
              <img src={c.imagen_url} alt={c.nombre} style={{ width: "100%", height: "160px", objectFit: "cover", borderRadius: "5px", marginBottom: "10px", display: "block" }} />
            ) : (
              <div style={{ width: "100%", height: "160px", objectFit: "cover", borderRadius: "5px", marginBottom: "10px", display: "flex", alignItems: "center", justifyContent: "center", background: "#f0f0f0", fontSize: "2rem" }}>🏟️</div>
            )}
            <strong>{c.nombre}</strong> — {c.deporte} — Bs {c.precio_hora}/hora
            {c.techada ? " (techada)" : ""} — Estado: {c.estado}
            <br />
            <Link to={`/reservar/${c.id}`} style={{ display: "inline-block", marginTop: "10px" }}>
              <button style={{ padding: "5px 10px", cursor: "pointer" }}>Reservar</button>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default CanchasPage;