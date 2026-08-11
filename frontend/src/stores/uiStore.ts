import { create } from 'zustand'

interface Toast {
  id: string
  message: string
  type: 'info' | 'success' | 'warning' | 'error'
}

interface UIStore {
  sidebarCollapsed: boolean
  darkMode: boolean
  toasts: Toast[]
  toggleSidebar: () => void
  toggleDarkMode: () => void
  setDarkMode: (dark: boolean) => void
  addToast: (toast: Omit<Toast, 'id'>) => void
  removeToast: (id: string) => void
}

export const useUIStore = create<UIStore>()((set) => ({
  sidebarCollapsed: false,
  darkMode: localStorage.getItem('soc-dark-mode') === 'true',
  toasts: [] as Toast[],
  toggleSidebar: () =>
    set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  toggleDarkMode: () =>
    set((s) => {
      const next = !s.darkMode
      localStorage.setItem('soc-dark-mode', String(next))
      return { darkMode: next }
    }),
  setDarkMode: (dark: boolean) => {
    localStorage.setItem('soc-dark-mode', String(dark))
    set({ darkMode: dark })
  },
  addToast: (toast: Omit<Toast, 'id'>) =>
    set((s) => ({
      toasts: [...s.toasts, { ...toast, id: crypto.randomUUID() }],
    })),
  removeToast: (id: string) =>
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}))
