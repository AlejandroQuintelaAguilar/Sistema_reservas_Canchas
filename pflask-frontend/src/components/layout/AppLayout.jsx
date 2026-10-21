import { useState } from "react";
import { useNavigate, NavLink } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard", ic: "▦" },
  { to: "/eventos", label: "Eventos", ic: "✓" },
  { to: "/reservas", label: "Reservas", ic: "▤" },
  { to: "/pagos", label: "Pagos", ic: "₳", roles: ["admin", "administrador", "empleado"] },
  { to: "/admin/eventos", label: "Administración", ic: "◔", roles: ["admin", "administrador", "empleado"] },
  { to: "/reportes", label: "Reportes", ic: "📊", roles: ["admin", "administrador"] },
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

  const currentRole = user?.role || user?.rol;
  const items = NAV_ITEMS.filter(
    (item) => !item.roles || item.roles.includes(currentRole),
  );

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
