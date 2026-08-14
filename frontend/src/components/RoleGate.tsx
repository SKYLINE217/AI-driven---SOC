import { useAuthStore } from "@/stores/authStore"
import type { Role } from "@/types"

interface RoleGateProps {
  requiredRole: Role
  children: React.ReactNode
  fallbackTooltip?: string
}

export function RoleGate({ requiredRole, children, fallbackTooltip }: RoleGateProps) {
  const hasRole = useAuthStore((s) => s.hasRole)
  if (hasRole(requiredRole, "approver")) return <>{children}</>
  return (
    <span title={fallbackTooltip ?? `Requires ${requiredRole.replace("_", " ")} role`}
      style={{ cursor: "not-allowed" }}>
      <span style={{ pointerEvents: "none", opacity: 0.4 }}>{children}</span>
    </span>
  )
}
