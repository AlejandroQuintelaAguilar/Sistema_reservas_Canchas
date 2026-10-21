import ForgotPasswordPage from './pages/ForgotPasswordPage';
import { Routes, Route } from 'react-router-dom';
import ResetPasswordPage from './pages/ResetPasswordPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import ReservasPage from './pages/ReservasPage';
import ReportesPage from './pages/ReportesPage';
import PagosPage from './pages/PagosPage.tsx';
import { ProtectedRoute } from './components/ProtectedRoute';
import UsuarioEventosPage from './pages/UsuarioEventosPage';
import AdminEventosPage from './pages/AdminEventosPage';
import PortalPublicoPage from './pages/PortalPublicoPage';

function App() {
  return (
    <Routes>

      {/* ============================================
          PORTAL PÚBLICO
          ============================================ */}
      <Route
        path="/"
        element={<PortalPublicoPage />}
      />

      {/* ============================================
          AUTENTICACIÓN
          ============================================ */}
      <Route
        path="/login"
        element={<LoginPage />}
      />

      <Route
        path="/register"
        element={<RegisterPage />}
      />

      <Route
        path="/forgot-password"
        element={<ForgotPasswordPage />}
      />

      <Route
        path="/reset-password/:token"
        element={<ResetPasswordPage />}
      />

      {/* ============================================
          DASHBOARD
          ============================================ */}
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        }
      />

      {/* ============================================
          EVENTOS
          ============================================ */}
      <Route
        path="/eventos"
        element={
          <ProtectedRoute>
            <UsuarioEventosPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/admin/eventos"
        element={
          <ProtectedRoute
            allowedRoles={[
              'admin',
              'administrador',
              'empleado'
            ]}
          >
            <AdminEventosPage />
          </ProtectedRoute>
        }
      />

      {/* ============================================
          REPORTES (solo admin)
          ============================================ */}
      <Route
        path="/reportes"
        element={
          <ProtectedRoute
            allowedRoles={[
              'admin',
              'administrador'
            ]}
          >
            <ReportesPage />
          </ProtectedRoute>
        }
      />

      {/* ============================================
          RESERVAS
          ============================================ */}
      <Route
        path="/reservas"
        element={
          <ProtectedRoute>
            <ReservasPage />
          </ProtectedRoute>
        }
      />

      {/* ============================================
          USUARIOS
          ============================================ */}
      <Route
        path="/usuarios"
        element={
          <ProtectedRoute
            allowedRoles={[
              'admin',
              'administrador'
            ]}
          >
            <DashboardPage />
          </ProtectedRoute>
        }
      />

    {/* ============================================
          PAGOS
          ============================================ */}
      <Route
        path="/pagos"
        element={
          <ProtectedRoute
            allowedRoles={[
              'admin',
              'administrador',
              'empleado'
            ]}
          >
            <PagosPage />
          </ProtectedRoute>
        }
      />

    </Routes>
  );
}

export default App;
