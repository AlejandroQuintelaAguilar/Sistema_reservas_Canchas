import { useState } from "react";
import { useForm } from "react-hook-form";
import { yupResolver } from "@hookform/resolvers/yup";
import * as yup from "yup";
import { useNavigate, Link } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import { authService } from "../services/authService";
import "./LoginInspired.css";

const schema = yup
  .object({
    email: yup.string().required("El correo es obligatorio."),
    password: yup.string().required("La contraseña es obligatoria."),
  })
  .required();

const LoginPage = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({
    resolver: yupResolver(schema),
  });

  const [errorMsg, setErrorMsg] = useState("");

  const onSubmit = async (data) => {
    setErrorMsg("");
    try {
      const userData = await authService.login(data);
      login(userData);
      navigate("/dashboard");
    } catch (error) {
      if (!error.response) {
        setErrorMsg(
          "No se pudo conectar con el servidor. ¿Está Flask corriendo en el puerto 5000?",
        );
      } else if (error.response.status === 401) {
        setErrorMsg("Credenciales inválidas. Inténtalo de nuevo.");
      } else {
        setErrorMsg(error.response.data?.error || "Error al iniciar sesión.");
      }
    }
  };

  return (
    <main className="login-inspired-page">
      <section className="login-inspired-card">
        <div className="login-inspired-cover">
          <Link to="/" className="login-inspired-back">
            ← Volver
          </Link>
          <span className="login-inspired-status">Sistema de Canchas ●</span>
          <div className="login-inspired-cover-content">
            <span className="login-inspired-football">⚽</span>
            <h1>¡Bienvenido!</h1>
            <p>Accede y reserva tu cancha en segundos.</p>
          </div>
          <img
            className="login-inspired-field-photo"
            src="https://images.unsplash.com/photo-1522778119026-d647f0596c20?auto=format&fit=crop&w=900&q=85"
            alt="Cancha de fútbol iluminada"
          />
        </div>

        <div className="login-inspired-form">
          <div className="login-inspired-form-header">
            <h2>Iniciar sesión</h2>
            <p className="login-inspired-subtitle">
              Ingresa tus credenciales para continuar.
            </p>
          </div>

          {errorMsg && <div className="login-inspired-error">{errorMsg}</div>}

          <form onSubmit={handleSubmit(onSubmit)}>
            <div className="login-inspired-field">
              <label className="login-inspired-label" htmlFor="email">
                Correo o usuario
              </label>
              <input
                id="email"
                type="text"
                className="login-inspired-input"
                placeholder="correo@ejemplo.com"
                {...register("email")}
              />
              {errors.email && (
                <span className="login-inspired-error-field">
                  {errors.email.message}
                </span>
              )}
            </div>

            <div className="login-inspired-field">
              <label className="login-inspired-label" htmlFor="password">
                Contraseña
              </label>
              <input
                id="password"
                type="password"
                className="login-inspired-input"
                placeholder="••••••••"
                {...register("password")}
              />
              {errors.password && (
                <span className="login-inspired-error-field">
                  {errors.password.message}
                </span>
              )}
            </div>

            <Link to="/forgot-password" className="login-inspired-forgot">
              ¿Olvidaste tu contraseña?
            </Link>

            <button type="submit" className="login-inspired-submit">
              Iniciar sesión
            </button>
          </form>

          <div className="login-inspired-separator">
            <span />
            <small>o</small>
            <span />
          </div>

          <div className="login-inspired-gallery">
            <img
              src="https://images.unsplash.com/photo-1459865264687-595d652de67e?auto=format&fit=crop&w=300&q=80"
              alt="Cancha 1"
            />
            <img
              src="https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=300&q=80"
              alt="Cancha 2"
            />
            <img
              src="https://images.unsplash.com/photo-1517927033932-b3d18e61fb3a?auto=format&fit=crop&w=300&q=80"
              alt="Cancha 3"
            />
          </div>

          <p className="login-inspired-switch">
            ¿No tienes cuenta? <Link to="/register">Regístrate</Link>
          </p>
        </div>
      </section>
    </main>
  );
};

export default LoginPage;
