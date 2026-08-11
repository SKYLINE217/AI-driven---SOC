import { create } from 'zustand';
import type { Alert } from '../types';

interface AlertStore {
  alerts: Alert[];
  wsStatus: 'connected' | 'reconnecting' | 'disconnected';
  newAlertCount: number;
  
  prependAlert: (alert: Alert) => void;
  setAlerts: (alerts: Alert[]) => void;
  setWsStatus: (status: 'connected' | 'reconnecting' | 'disconnected') => void;
  resetNewAlertCount: () => void;
}

export const useAlertStore = create<AlertStore>((set) => ({
  alerts: [],
  wsStatus: 'disconnected',
  newAlertCount: 0,
  
  prependAlert: (alert) => 
    set((state) => ({ 
      alerts: [alert, ...state.alerts],
      newAlertCount: state.newAlertCount + 1
    })),
    
  setAlerts: (alerts) => set({ alerts }),
  
  setWsStatus: (wsStatus) => set({ wsStatus }),
  
  resetNewAlertCount: () => set({ newAlertCount: 0 })
}));
