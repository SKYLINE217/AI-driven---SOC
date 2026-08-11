/**
 * useAuth — Authentication hook wrapping the authStore.
 *
 * Handles: login API call → JWT storage → redirect.
 * Production path: swap the fetch call for an OIDC/SSO redirect.
 */

import { useAuthStore } from '../stores/authStore';
import type { Role } from '../types';

export function useAuth() {
  const { token, role, email, setAuth, clearAuth } = useAuthStore();

  const login = async (userEmail: string, userRole: Role): Promise<void> => {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: userEmail, role: userRole }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Login failed' }));
      throw new Error(err.detail || 'Login failed');
    }

    const data = await res.json();
    setAuth(data.access_token, data.role as Role, data.email);
  };

  const logout = (): void => {
    clearAuth();
  };

  return {
    isAuthenticated: !!token,
    token,
    role,
    email,
    login,
    logout,
  };
}
