import { useState } from "react";
import { useForm } from "react-hook-form";
import { yupResolver } from "@hookform/resolvers/yup";
import * as yup from "yup";
import { Link } from "react-router-dom";

import { authService } from "../services/authService";
import {
  CI_RE,
  CELULAR_RE,
  USERNAME_RE,
  REQUISITOS_PASSWORD,
  esquemaContrasena,
} from "../utils/validaciones";

const schema = yup
  .object({
    // trim antes de required: el required de yup rechaza "" pero no "   ".
    nombre: yup.string().trim().required("El nombre es obligatorio."),
    apellido: yup.string().trim().required("El apellido es obligatorio."),
    ci: yup
      .string()
      .trim()
      .required("El CI es obligatorio.")
      .matches(CI_RE, "El CI debe tener entre 4 y 10 dígitos, sin letras."),
    celular: yup
      .string()
      .trim()
      .required("El celular es obligatorio.")
      .matches(CELULAR_RE, "El celular debe tener entre 7 y 15 dígitos."),
    email: yup
      .string()
      .trim()
      .required("El correo es obligatorio.")
      .email("Debe ser un correo válido."),
    username: yup
      .string()
      .trim()
      .required("El nombre de usuario es obligatorio.")
      .matches(USERNAME_RE, "Entre 4 y 30 caracteres: letras, números, punto, guion o guion bajo."),
    ...esquemaContrasena(yup, "password", "confirmPassword"),
  })
  .required();

const RegisterPage = () => {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({ resolver: yupResolver(schema) });

  const [message, setMessage] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  const onSubmit = async (data) => {
    setMessage("");
    setErrorMsg("");
    try {
      await authService.registro(data);
      setMessage(
        "¡Cuenta creada exitosamente! Serás redirigido al inicio de sesión...",
      );
      setTimeout(() => {
        window.location.href = "/login";
      }, 3000);
    } catch (error) {
      setErrorMsg(
        error.response?.data?.error ||
          error.response?.data?.message ||
          "No se pudo crear la cuenta. Verifica el servidor backend.",
      );
    }
  };

  return (
    <div className="login-container">
      <Link to="/login" className="back-link">← Volver</Link>
      <div className="login-card login-card-wide">
        <div className="login-header">
          <div className="login-logo">C</div>
          <h1>Crear cuenta</h1>
          <p>Regístrate para reservar canchas</p>
        </div>

        {errorMsg && <div className="mensaje error">{errorMsg}</div>}
        {message && <div className="mensaje success">{message}</div>}

        <form onSubmit={handleSubmit(onSubmit)}>
          <div className="form-row">
            <div className="form-group">
              <label>Nombre</label>
              <input type="text" placeholder="Juan" {...register("nombre")} />
              {errors.nombre && (
                <span className="campo-error">{errors.nombre.message}</span>
              )}
            </div>
            <div className="form-group">
              <label>Apellido</label>
              <input
                type="text"
                placeholder="Pérez"
                {...register("apellido")}
              />
              {errors.apellido && (
                <span className="campo-error">{errors.apellido.message}</span>
              )}
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>CI</label>
              <input type="text" placeholder="1234567" {...register("ci")} />
              {errors.ci && (
                <span className="campo-error">{errors.ci.message}</span>
              )}
            </div>
            <div className="form-group">
              <label>Celular</label>
              <input
                type="text"
                placeholder="+591 70000000"
                {...register("celular")}
              />
              {errors.celular && (
                <span className="campo-error">{errors.celular.message}</span>
              )}
            </div>
          </div>

          <div className="form-group">
            <label>Correo</label>
            <input
              type="email"
              placeholder="correo@ejemplo.com"
              {...register("email")}
            />
            {errors.email && (
              <span className="campo-error">{errors.email.message}</span>
            )}
          </div>

          <div className="form-group">
            <label>Nombre de usuario</label>
            <input
              type="text"
              placeholder="juanp123"
              {...register("username")}
            />
            {errors.username && (
              <span className="campo-error">{errors.username.message}</span>
            )}
          </div>

          <div className="form-group">
            <label>Contraseña</label>
            <input
              type="password"
              autoComplete="new-password"
              placeholder="Mínimo 8 caracteres"
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
              {...register("confirmPassword")}
            />
            {errors.confirmPassword && (
              <span className="campo-error">
                {errors.confirmPassword.message}
              </span>
            )}
          </div>

          <button type="submit" className="btn-primary btn-block">
            Crear cuenta
          </button>
        </form>

        <div className="login-links">
          <p>
            ¿Ya tienes cuenta? <Link to="/login">Inicia sesión</Link>
          </p>
        </div>
      </div>
    </div>
  );
};

export default RegisterPage;