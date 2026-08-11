import { create } from 'zustand';

export interface Toast {
  id: string;
  type: 'critical' | 'warning' | 'success' | 'info';
  message: string;
  duration?: number; // ms
}

interface UiStore {
  sidebarCollapsed: boolean;
  darkMode: boolean;
  toasts: Toast[];
  
  toggleSidebar: () => void;
  toggleDarkMode: () => void;
  addToast: (toast: Omit<Toast, 'id'>) => void;
  removeToast: (id: string) => void;
}

export const useUiStore = create<UiStore>((set) => ({
  sidebarCollapsed: false,
  darkMode: true,
  toasts: [],
  
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  
  toggleDarkMode: () => set((state) => {
    const nextMode = !state.darkMode;
    if (nextMode) {
      document.documentElement.setAttribute('data-theme', 'dark');
    } else {
      document.documentElement.setAttribute('data-theme', 'light');
    }
    return { darkMode: nextMode };
  }),
  
  addToast: (toastProps) => {
    const id = Math.random().toString(36).substring(2, 9);
    const toast = { ...toastProps, id };
    
    set((state) => ({ toasts: [...state.toasts, toast] }));
    
    if (toast.duration !== 0) {
      setTimeout(() => {
        set((state) => ({ toasts: state.toasts.filter(t => t.id !== id) }));
      }, toast.duration || 5000);
    }
  },
  
  removeToast: (id) => set((state) => ({ toasts: state.toasts.filter(t => t.id !== id) }))
}));
