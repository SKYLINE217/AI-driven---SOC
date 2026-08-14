import { create } from "zustand"
import type { Alert, WsStatus } from "@/types"

interface AlertStore {
  alerts: Alert[]
  wsStatus: WsStatus
  newAlertCount: number
  prependAlert: (alert: Alert) => void
  setAlerts: (alerts: Alert[]) => void
  setWsStatus: (status: WsStatus) => void
  resetNewAlertCount: () => void
}

export const useAlertStore = create<AlertStore>((set) => ({
  alerts: [],
  wsStatus: "disconnected",
  newAlertCount: 0,
  prependAlert: (alert) =>
    set((s) => ({
      alerts: [alert, ...s.alerts].slice(0, 50),
      newAlertCount: s.newAlertCount + 1,
    })),
  setAlerts: (alerts) => set({ alerts }),
  setWsStatus: (wsStatus) => set({ wsStatus }),
  resetNewAlertCount: () => set({ newAlertCount: 0 }),
}))
