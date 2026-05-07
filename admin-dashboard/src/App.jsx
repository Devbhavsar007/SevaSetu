import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Layout from './components/Layout';
import DashboardPage from './pages/DashboardPage';
import NeedsPage from './pages/NeedsPage';
import MapPage from './pages/MapPage';
import VolunteersPage from './pages/VolunteersPage';
import BroadcastPage from './pages/BroadcastPage';
import OCRPage from './pages/OCRPage';
import MatchingPage from './pages/MatchingPage';
import LoginPage from './pages/LoginPage';
import InventoryPage from './pages/InventoryPage';
import AuditPage from './pages/AuditPage';

// Loading spinner component
function LoadingSpinner() {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      height: '100vh', background: 'var(--bg-primary)',
    }}>
      <div style={{
        width: 48, height: 48, border: '4px solid var(--border-color)',
        borderTopColor: 'var(--accent-green)', borderRadius: '50%',
        animation: 'spin 0.8s linear infinite',
      }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

// Protected route wrapper
function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return <LoadingSpinner />;
  if (!isAuthenticated) return <Navigate to="/login" />;
  return children;
}

// Login route — redirect if already authenticated
function LoginRoute() {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return <LoadingSpinner />;
  if (isAuthenticated) return <Navigate to="/" replace />;
  return <LoginPage />;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginRoute />} />
      <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route index element={<DashboardPage />} />
        <Route path="needs" element={<NeedsPage />} />
        <Route path="map" element={<MapPage />} />
        <Route path="volunteers" element={<VolunteersPage />} />
        <Route path="broadcast" element={<BroadcastPage />} />
        <Route path="ocr" element={<OCRPage />} />
        <Route path="matching/:needId?" element={<MatchingPage />} />
        <Route path="inventory" element={<InventoryPage />} />
        <Route path="audit" element={<AuditPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  );
}
