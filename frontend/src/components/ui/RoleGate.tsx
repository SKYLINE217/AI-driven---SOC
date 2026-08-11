/**
 * RoleGate — RBAC-enforced wrapper for action buttons.
 *
 * Client-side enforcement (UX only — prevents accidental clicks).
 * The real security control is the FastAPI `require_role()` dependency.
 * Per soc-triager-security: "the UI gate is not the real control."
 */

import type { ReactNode } from 'react';
import { useAuth } from '../../hooks/useAuth';
import type { Role } from '../../types';

const ROLE_LEVELS: Record<Role, number> = {
  analyst: 1,
  senior_analyst: 2,
  approver: 3,
};

interface RoleGateProps {
  requiredRole: Role;
  children: ReactNode;
  tooltip?: string;
}

export default function RoleGate({ requiredRole, children, tooltip }: RoleGateProps) {
  const { role } = useAuth();
  const currentLevel = ROLE_LEVELS[role ?? 'analyst'] ?? 0;
  const requiredLevel = ROLE_LEVELS[requiredRole];
  const allowed = currentLevel >= requiredLevel;

  if (allowed) return <>{children}</>;

  const defaultTooltip = `Only ${requiredRole.replace('_', ' ')}s can perform this action`;

  return (
    <div
      title={tooltip ?? defaultTooltip}
      style={{ display: 'inline-block', cursor: 'not-allowed' }}
      aria-label={tooltip ?? defaultTooltip}
    >
      <div style={{ pointerEvents: 'none', opacity: 0.4 }}>
        {children}
      </div>
    </div>
  );
}
