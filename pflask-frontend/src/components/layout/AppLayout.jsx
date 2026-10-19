import { useState } from "react";
import { useNavigate, NavLink } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";

// El backend permite operar la caja (abrir turno, arqueo, validar pagos) tanto
// al administrador como al empleado: ROLES_OPERACION en pagos_controller.
const ROLES_OPERACION_UI = ["admin", "administrador", "empleado"];
const ROLES_ADMIN_UI = ["admin", "administrador"];

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard", ic: "▦" },
  { to: "/eventos", label: "Eventos", ic: "✓" },
  { to: "/reservas", label: "Reservas", ic: "▤" },
  // Caja y pagos son el mismo modulo (PagosPage, con pestañas internas): una
  // sola entrada al menu. /caja queda como alias que redirige a /pagos para no
  // romper enlaces guardados.
  { to: "/pagos", label: "Caja y Pagos", ic: "₳", roles: ROLES_OPERACION_UI },
  { to: "/admin/canchas", label: "Canchas", ic: "◉", roles: ROLES_ADMIN_UI },
  // El empleado entra a programar eventos; editar y borrar los limita el
  // backend al administrador.
  { to: "/admin/eventos", label: "Administración", ic: "◔", roles: ROLES_OPERACION_UI },
  { to: "/reportes", label: "Reportes", ic: "📊", roles: ROLES_ADMIN_UI },
  { to: "/analitica", label: "Analitica", ic: "◧", roles: ROLES_ADMIN_UI },
];

export const AppLayout = ({ children, title = "Panel", subtitle = "" }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");

  const inicial =
    user?.nombre_completo?.trim()?.[0] ||
    user?.nombre?.[0] ||
    user?.username?.[0] ||
    "U";

  // "admin: true" es solo para el administrador. "roles: [...]" muestra el
  // enlace a quien figure en la lista. Si no tiene ninguno de los dos, es
  // visible para todos.
  const items = NAV_ITEMS.filter((item) => {
    if (item.admin) return ["admin", "administrador"].includes(user?.role);
    if (item.roles) return item.roles.includes(user?.role);
    return true;
  });

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="dot">C</span>
          Canchas
        </div>

        <div>
          <div className="nav-label">Menú</div>
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `nav-item ${isActive ? "active" : ""}`
              }
            >
              <span className="ic">{item.ic}</span>
              {item.label}
            </NavLink>
          ))}
        </div>

        <div>
          <div className="nav-label">General</div>
          <button className="nav-item" onClick={handleLogout}>
            <span className="ic">⏻</span>Cerrar sesión
          </button>
        </div>
      </aside>

      <main className="main">
        <div className="topbar">
          <div className="search">
            🔍<input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar..."
              disabled
              title="Buscador deshabilitado (no funcional)"
            />
          </div>
          <div className="user">
            <div className="avatar">{inicial}</div>
          </div>
        </div>

        <div className="header-row">
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <button
              className="btn-back"
              onClick={() => navigate(-1)}
              title="Volver a la pantalla anterior"
            >
              ←
            </button>
            <div>
              <h1>{title}</h1>
              {subtitle && <p className="subtitle">{subtitle}</p>}
            </div>
          </div>
        </div>

        {children}
      </main>
    </div>
  );
};

export default AppLayout;