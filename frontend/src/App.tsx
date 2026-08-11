import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AppShell } from '@/components/layout/AppShell'
import { lazy, Suspense } from 'react'

// Lazy-loaded pages
const AlertQueue = lazy(() => import('@/pages/AlertQueue'))
const IncidentDetail = lazy(() => import('@/pages/IncidentDetail'))
const Navigator = lazy(() => import('@/pages/Navigator'))
const OpsMetrics = lazy(() => import('@/pages/OpsMetrics'))
const PlaybookLibrary = lazy(() => import('@/pages/PlaybookLibrary'))
const Settings = lazy(() => import('@/pages/Settings'))
const LoginPage = lazy(() => import('@/pages/Login'))

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
})

function PageLoader() {
  return (
    <div className="page-stub">
      <div
        style={{
          width: 32,
          height: 32,
          border: '3px solid var(--border-secondary)',
          borderTopColor: 'var(--accent-primary)',
          borderRadius: '50%',
          animation: 'spin 0.8s linear infinite',
        }}
      />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            {/* Public route */}
            <Route path="/login" element={<LoginPage />} />

            {/* Protected routes — AppShell handles auth guard */}
            <Route element={<AppShell />}>
              <Route path="/alerts" element={<AlertQueue />} />
              <Route path="/incidents/:id" element={<IncidentDetail />} />
              <Route path="/incidents" element={<AlertQueue />} />
              <Route path="/navigator" element={<Navigator />} />
              <Route path="/ops" element={<OpsMetrics />} />
              <Route path="/playbooks" element={<PlaybookLibrary />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/" element={<Navigate to="/alerts" replace />} />
              <Route path="*" element={<Navigate to="/alerts" replace />} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
