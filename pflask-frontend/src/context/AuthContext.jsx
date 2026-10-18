import { createContext, useState, useContext } from 'react';
import { authService } from '../services/authService';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(() => {
    const userData = localStorage.getItem('userData');
    if (userData) return JSON.parse(userData);
    const token = localStorage.getItem('token');
    const role = localStorage.getItem('role');
    return token && role ? { token, role } : null;
  });

  const login = (userData) => {
    localStorage.setItem('userData', JSON.stringify(userData));
    localStorage.setItem('token', userData.token);
    localStorage.setItem('role', userData.role);
    setUser(userData);
  };

  const logout = () => {
    authService.logout().catch(() => {});
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    localStorage.removeItem('userData');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);