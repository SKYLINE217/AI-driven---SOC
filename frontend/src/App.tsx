import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import AppShell from './components/layout/AppShell';
import AlertQueue from './pages/AlertQueue';
import IncidentDetail from './pages/IncidentDetail';
import OpsMetrics from './pages/OpsMetrics';
import Navigator from './pages/Navigator';
import PlaybookLibrary from './pages/PlaybookLibrary';
import Settings from './pages/Settings';
import Login from './pages/Login';
import './styles/globals.css';
import { useEffect } from 'react';
import { useUiStore } from './stores/uiStore';
import { useAuthStore } from './stores/authStore';

/** Route guard: redirects unauthenticated users to /login */
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore(state => state.token);
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function App() {
  const darkMode = useUiStore(state => state.darkMode);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', darkMode ? 'dark' : 'light');
  }, [darkMode]);

  return (
    <Router>
      <Routes>
        {/* Public routes */}
        <Route path="/login" element={<Login />} />

        {/* Protected routes — require JWT */}
        <Route path="/" element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }>
          <Route index element={<Navigate to="/alerts" replace />} />
          <Route path="alerts" element={<AlertQueue />} />
          <Route path="incidents" element={<Navigate to="/alerts" replace />} />
          <Route path="incidents/:id" element={<IncidentDetail />} />
          <Route path="navigator" element={<Navigator />} />
          <Route path="ops" element={<OpsMetrics />} />
          <Route path="playbooks" element={<PlaybookLibrary />} />
          <Route path="settings" element={<Settings />} />
        </Route>

        {/* Catch-all */}
        <Route path="*" element={<Navigate to="/alerts" replace />} />
      </Routes>
    </Router>
  );
}

export default App;
