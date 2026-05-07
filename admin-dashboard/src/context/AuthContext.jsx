import { createContext, useContext, useState, useEffect } from 'react';
import { auth as authApi, setToken, clearAuth, getStoredUser, setStoredUser, getToken } from '../services/api';

const AuthContext = createContext(null);

// Hardcoded admin for dev-token bypass
const DEV_ADMIN_USER = {
  id: 'dev-admin-001',
  email: 'admin@sevasetu.org',
  name: 'Admin',
  role: 'admin',
  is_active: true,
};

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // On mount, validate existing token
  useEffect(() => {
    const validateAuth = async () => {
      const token = getToken();
      const storedUser = getStoredUser();

      if (!token) {
        setLoading(false);
        return;
      }

      // DEV MODE: dev-token bypass — skip /auth/me/ validation
      if (token === 'dev-token') {
        setUser(storedUser || DEV_ADMIN_USER);
        if (!storedUser) setStoredUser(DEV_ADMIN_USER);
        setLoading(false);
        return;
      }

      // Validate JWT with backend
      try {
        const me = await authApi.getMe();
        setUser(me);
        setStoredUser(me);
      } catch (err) {
        console.warn('Token validation failed:', err);
        clearAuth();
        setUser(null);
      }

      setLoading(false);
    };

    validateAuth();
  }, []);

  // Google login
  const login = async (idToken) => {
    setLoading(true);
    try {
      const res = await authApi.googleLogin(idToken, 'admin');
      setToken(res.access_token);
      setStoredUser(res.user);
      setUser(res.user);
      return res;
    } finally {
      setLoading(false);
    }
  };

  // Email login
  const emailLogin = async (email, password) => {
    setLoading(true);
    try {
      const res = await authApi.emailLogin(email, password);
      setToken(res.access_token);
      setStoredUser(res.user);
      setUser(res.user);
      return res;
    } finally {
      setLoading(false);
    }
  };

  // Email register
  const emailRegister = async (email, password, name) => {
    setLoading(true);
    try {
      const res = await authApi.emailRegister(email, password, name, 'admin');
      setToken(res.access_token);
      setStoredUser(res.user);
      setUser(res.user);
      return res;
    } finally {
      setLoading(false);
    }
  };

  // Dev mode login
  const devLogin = () => {
    setToken('dev-token');
    setStoredUser(DEV_ADMIN_USER);
    setUser(DEV_ADMIN_USER);
  };

  // Logout
  const logout = async () => {
    try {
      await authApi.logout();
    } catch (e) {
      // Ignore — server may not be reachable
    }
    clearAuth();
    setUser(null);
  };

  const isAuthenticated = !!user;

  return (
    <AuthContext.Provider value={{ user, loading, isAuthenticated, login, emailLogin, emailRegister, devLogin, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
