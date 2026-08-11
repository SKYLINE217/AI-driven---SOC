import { create } from 'zustand'
import type { Role } from '@/types'

interface AuthState {
  token: string | null
  role: Role | null
  email: string | null
}

interface AuthActions {
  setAuth: (token: string, role: Role, email: string) => void
  clearAuth: () => void
  hasRole: (...roles: Role[]) => boolean
}

type AuthStore = AuthState & AuthActions

const ROLE_HIERARCHY: Record<Role, Role[]> = {
  analyst: ['analyst'],
  senior_analyst: ['analyst', 'senior_analyst'],
  approver: ['analyst', 'senior_analyst', 'approver'],
}

export const useAuthStore = create<AuthStore>()((set, get) => ({
  token: null,
  role: null,
  email: null,
  setAuth: (token: string, role: Role, email: string) =>
    set({ token, role, email }),
  clearAuth: () => set({ token: null, role: null, email: null }),
  hasRole: (...roles: Role[]) => {
    const currentRole = get().role
    if (!currentRole) return false
    const effective = ROLE_HIERARCHY[currentRole] ?? []
    return roles.some((r) => effective.includes(r))
  },
}))
