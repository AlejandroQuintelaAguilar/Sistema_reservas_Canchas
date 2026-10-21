import axiosClient from '../api/axiosClient';

export const authService = {
  login: async (credentials) => {
    const response = await axiosClient.post('/auth/login', {
      email: credentials.email,
      username: credentials.email,
      contrasena: credentials.password,
      password: credentials.password,
    });
    return response.data;
  },

  registro: async (userData) => {
    const response = await axiosClient.post('/auth/register', {
      nombre: userData.nombre,
      apellido: userData.apellido,
      ci: userData.ci,
      celular: userData.celular,
      email: userData.email,
      username: userData.username,
      contrasena: userData.password,
      password: userData.password,
    });
    return response.data;
  },

  solicitarRecuperacion: async (email) => {
    const response = await axiosClient.post('/auth/recover', { email });
    return response.data;
  },

  restablecerContrasena: async (token, newPassword) => {
    const response = await axiosClient.post('/auth/reset', {
      token,
      contrasena: newPassword,
      password: newPassword,
    });
    return response.data;
  },

  logout: async () => {
    const response = await axiosClient.post('/auth/logout');
    return response.data;
  },

  obtenerUsuarios: async () => {
    const response = await axiosClient.get('/admin/users');
    return response.data;
  },

  crearUsuario: async (userData) => {
    return authService.registro(userData);
  },

  actualizarUsuario: async (id, userData) => {
    const response = await axiosClient.put(`/admin/users/${id}`, userData);
    return response.data;
  },

  eliminarUsuario: async (id) => {
    const response = await axiosClient.delete(`/admin/users/${id}`);
    return response.data;
  }
};
