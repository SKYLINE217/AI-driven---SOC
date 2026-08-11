import type { ReactNode } from 'react'
import { useAuthStore } from '@/stores/authStore'
import type { Role } from '@/types'

const ROLE_HIERARCHY: Record<Role, Role[]> = {
  analyst: ['analyst'],
  senior_analyst: ['analyst', 'senior_analyst'],
  approver: ['analyst', 'senior_analyst', 'approver'],
}

interface RoleGateProps {
  children: ReactNode
  requiredRole: Role
  fallback?: ReactNode
}

export function RoleGate({ children, requiredRole, fallback = null }: RoleGateProps) {
  const currentRole = useAuthStore((s) => s.role)

  if (!currentRole) return <>{fallback}</>

  const effectiveRoles = ROLE_HIERARCHY[currentRole] ?? []
  
  if (effectiveRoles.includes(requiredRole)) {
    return <>{children}</>
  }

  return <>{fallback}</>
}
