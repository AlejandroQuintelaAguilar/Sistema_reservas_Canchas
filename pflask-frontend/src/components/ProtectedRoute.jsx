import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export const ProtectedRoute = ({ children, allowedRoles }) => {
  const { user } = useAuth(); // Consultamos el estado global de la sesión

  // 1. Si no hay usuario logueado, lo pateamos de vuelta al Login
  if (!user) {
    return <Navigate to="/login" replace />;
  }

  // 2. Si la ruta exige un rol específico (ej. "admin") y el usuario no lo tiene, lo bloqueamos
  const currentRole = user.role || user.rol;
  if (allowedRoles && !allowedRoles.includes(currentRole)) {
    return <Navigate to="/unauthorized" replace />; 
  }

  // 3. Si pasa los filtros, renderizamos la pantalla que solicitó
  return children;
};
