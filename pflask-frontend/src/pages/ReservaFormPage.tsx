import { useState } from "react";
import type { FormEvent } from "react"; // <--- Se importa como "type"
import { useParams, useNavigate, Link } from "react-router-dom";
import { api } from "../services/api";

function ReservaFormPage() {
  const { idCancha } = useParams();
  const navigate = useNavigate();
  
  const [fecha, setFecha] = useState("");
  const [horaInicio, setHoraInicio] = useState("");
  const [horaFin, setHoraFin] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setEnviando(true);

    try {
      await api.post("/reservas", {
        id_cancha: Number(idCancha),
        fecha,
        hora_inicio: horaInicio,
        hora_fin: horaFin,
      });
      alert("¡Reserva creada con éxito!");
      navigate("/mis-reservas"); // Redirige al historial
    } catch (err: any) {
      // Muestra el error que envía Flask (ej. "La cancha ya está ocupada...")
      setError(err.response?.data?.error || "Error al conectar con el servidor.");
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div style={{ padding: "20px", maxWidth: "400px" }}>
      <h2>Reservar Cancha #{idCancha}</h2>
      <Link to="/" style={{ display: "inline-block", marginBottom: "15px" }}>← Volver a canchas</Link>
      
      {error && <p style={{ color: "red", padding: "10px", background: "#ffeeee", borderRadius: "5px" }}>{error}</p>}
      
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "15px" }}>
        <div>
          <label style={{ display: "block", marginBottom: "5px" }}>Fecha:</label>
          <input 
            type="date" 
            value={fecha} 
            onChange={(e) => setFecha(e.target.value)} 
            required 
            style={{ width: "100%", padding: "8px" }}
          />
        </div>
        <div>
          <label style={{ display: "block", marginBottom: "5px" }}>Hora Inicio:</label>
          <input 
            type="time" 
            value={horaInicio} 
            onChange={(e) => setHoraInicio(e.target.value)} 
            required 
            style={{ width: "100%", padding: "8px" }}
          />
        </div>
        <div>
          <label style={{ display: "block", marginBottom: "5px" }}>Hora Fin:</label>
          <input 
            type="time" 
            value={horaFin} 
            onChange={(e) => setHoraFin(e.target.value)} 
            required 
            style={{ width: "100%", padding: "8px" }}
          />
        </div>
        <button 
          type="submit" 
          disabled={enviando}
          style={{ padding: "10px", background: "#0F7F82", color: "white", border: "none", borderRadius: "999px", cursor: "pointer" }}
        >
          {enviando ? "Guardando..." : "Confirmar Reserva"}
        </button>
      </form>
    </div>
  );
}

export default ReservaFormPage;