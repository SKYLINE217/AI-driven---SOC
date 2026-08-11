import { useEffect } from 'react'
import { Outlet, Navigate } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { ToastContainer } from '@/components/ToastContainer'
import { useUIStore } from '@/stores/uiStore'
import { useAuthStore } from '@/stores/authStore'
import { useAlertsFeed } from '@/hooks/useAlertsFeed'

export function AppShell() {
  const darkMode = useUIStore((s) => s.darkMode)
  const token = useAuthStore((s) => s.token)

  // Apply dark mode to document root
  useEffect(() => {
    document.documentElement.setAttribute(
      'data-theme',
      darkMode ? 'dark' : 'light'
    )
  }, [darkMode])

  // Live WebSocket feed — only connects when auth token is present
  useAlertsFeed()

  // Redirect unauthenticated users to login
  if (!token) {
    return <Navigate to="/login" replace />
  }

  return (
    <div className="app-layout">
      <Sidebar />
      <div className="app-main">
        <TopBar />
        <main className="app-content">
          <Outlet />
        </main>
      </div>
      <ToastContainer />
    </div>
  )
}
