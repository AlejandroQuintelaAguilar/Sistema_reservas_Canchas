import { useState } from "react";
import { useForm } from "react-hook-form";
import { yupResolver } from "@hookform/resolvers/yup";
import * as yup from "yup";
import { useParams, useNavigate, Link } from "react-router-dom";

import { authService } from "../services/authService";
import { REQUISITOS_PASSWORD, esquemaContrasena } from "../utils/validaciones";

const schema = yup
  .object(esquemaContrasena(yup, "password", "confirmPassword"))
  .required();

const ResetPasswordPage = () => {
  const { token } = useParams();
  const navigate = useNavigate();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({ resolver: yupResolver(schema) });

  const [message, setMessage] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  // Sin token el enlace no sirve: /reset-password a secas llegaria al backend
  // con el campo omitido y un 400 sin explicación.
  const tokenValido = Boolean(String(token || "").trim());

  const onSubmit = async (data) => {
    setMessage("");
    setErrorMsg("");
    if (!tokenValido) {
      setErrorMsg("El enlace no es válido o ya expiró. Pide uno nuevo.");
      return;
    }
    try {
      await authService.restablecerContrasena(token, data.password);
      setMessage("Contraseña actualizada. Redirigiendo al inicio de sesión...");
      setTimeout(() => navigate("/login"), 3000);
    } catch (error) {
      setErrorMsg(
        !error.response
          ? "No se pudo conectar con el servidor."
          : error.response.data?.error ||
              "El enlace no es válido o ya expiró.",
      );
    }
  };

  return (
    <div className="login-container">
      <Link to="/login" className="back-link">← Volver</Link>
      <div className="login-card">
        <div className="login-header">
          <div className="login-logo">C</div>
          <h1>Restablecer contraseña</h1>
          <p>Escribe tu nueva contraseña</p>
        </div>

        {!tokenValido && (
          <div className="mensaje error">
            El enlace no es válido o ya expiró. Pide uno nuevo desde{" "}
            <Link to="/forgot-password">olvidé mi contraseña</Link>.
          </div>
        )}
        {errorMsg && <div className="mensaje error">{errorMsg}</div>}
        {message && <div className="mensaje success">{message}</div>}

        <form onSubmit={handleSubmit(onSubmit)}>
          <div className="form-group">
            <label>Nueva contraseña</label>
            <input
              type="password"
              autoComplete="new-password"
              placeholder="Mínimo 8 caracteres"
              disabled={!tokenValido}
              {...register("password")}
            />
            {errors.password && (
              <span className="campo-error">{errors.password.message}</span>
            )}
            {!errors.password && (
              <small className="hint">{REQUISITOS_PASSWORD}</small>
            )}
          </div>

          <div className="form-group">
            <label>Confirmar contraseña</label>
            <input
              type="password"
              autoComplete="new-password"
              placeholder="Repite la contraseña"
              disabled={!tokenValido}
              {...register("confirmPassword")}
            />
            {errors.confirmPassword && (
              <span className="campo-error">
                {errors.confirmPassword.message}
              </span>
            )}
          </div>

          <button type="submit" className="btn-primary btn-block" disabled={!tokenValido}>
            Restablecer contraseña
          </button>
        </form>

        <div className="login-links">
          <p>
            <Link to="/login">← Volver al inicio de sesión</Link>
          </p>
        </div>
      </div>
    </div>
  );
};

export default ResetPasswordPage;