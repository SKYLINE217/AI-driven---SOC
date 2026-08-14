import { create } from "zustand"
import type { Role } from "@/types"

interface AuthStore {
  token: string | null
  role: Role
  email: string | null
  setAuth: (token: string, role: Role, email: string) => void
  clearAuth: () => void
  hasRole: (...roles: Role[]) => boolean
  setRole: (role: Role) => void
}

export const useAuthStore = create<AuthStore>((set, get) => ({
  token: null,
  role: "analyst",
  email: null,
  setAuth: (token, role, email) => set({ token, role, email }),
  clearAuth: () => set({ token: null, role: "analyst", email: null }),
  hasRole: (...roles) => roles.includes(get().role),
  setRole: (role) => set({ role }),
}))
