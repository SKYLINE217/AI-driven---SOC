import { create } from 'zustand';
import type { AuthState, Role } from '../types';

interface AuthStore extends AuthState {
  setAuth: (token: string, role: Role, email: string) => void;
  clearAuth: () => void;
  hasRole: (...roles: Role[]) => boolean;
}

export const useAuthStore = create<AuthStore>((set, get) => ({
  token: null,
  role: null,
  email: null,
  
  setAuth: (token, role, email) => {
    set({ token, role, email });
  },
  
  clearAuth: () => {
    set({ token: null, role: null, email: null });
  },
  
  hasRole: (...roles) => {
    const { role } = get();
    if (!role) return false;
    // Approvers can do what analysts can do, etc., but for simplicity we check if role is in array
    // Or we map roles to privileges. Let's just check exact match or assume approver > senior > analyst.
    const roleLevels = { analyst: 1, senior_analyst: 2, approver: 3 };
    const currentLevel = roleLevels[role] || 0;
    
    return roles.some(r => currentLevel >= (roleLevels[r] || 0));
  }
}));
