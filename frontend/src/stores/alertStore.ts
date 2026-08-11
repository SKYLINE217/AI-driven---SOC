import { create } from 'zustand'
import type { Alert, WsStatus } from '@/types'

interface AlertStore {
  alerts: Alert[]
  wsStatus: WsStatus
  newAlertCount: number
  prependAlert: (alert: Alert) => void
  setAlerts: (alerts: Alert[]) => void
  updateAlertStatus: (alertId: string, status: Alert['status']) => void
  setWsStatus: (status: WsStatus) => void
  resetNewAlertCount: () => void
}

export const useAlertStore = create<AlertStore>()((set) => ({
  alerts: [],
  wsStatus: 'disconnected' as WsStatus,
  newAlertCount: 0,
  prependAlert: (alert: Alert) =>
    set((s) => ({
      alerts: [alert, ...s.alerts],
      newAlertCount: s.newAlertCount + 1,
    })),
  setAlerts: (alerts: Alert[]) => set({ alerts }),
  updateAlertStatus: (alertId: string, status: Alert['status']) =>
    set((s) => ({
      alerts: s.alerts.map((a) =>
        a.id === alertId ? { ...a, status } : a
      ),
    })),
  setWsStatus: (wsStatus: WsStatus) => set({ wsStatus }),
  resetNewAlertCount: () => set({ newAlertCount: 0 }),
}))
