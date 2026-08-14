import { create } from "zustand"
import type { Toast } from "@/types"

interface UIStore {
  sidebarCollapsed: boolean
  darkMode: boolean
  toasts: Toast[]
  toggleSidebar: () => void
  setDarkMode: (v: boolean) => void
  addToast: (toast: Omit<Toast, "id">) => void
  removeToast: (id: string) => void
}

const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches

export const useUIStore = create<UIStore>((set) => ({
  sidebarCollapsed: false,
  darkMode: prefersDark,
  toasts: [],
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setDarkMode: (darkMode) => set({ darkMode }),
  addToast: (toast) =>
    set((s) => ({
      toasts: [...s.toasts, { ...toast, id: crypto.randomUUID() }],
    })),
  removeToast: (id) =>
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}))
