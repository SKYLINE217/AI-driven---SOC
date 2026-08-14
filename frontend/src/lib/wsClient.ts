import { useAlertStore } from "@/stores/alertStore"
import { useUIStore } from "@/stores/uiStore"
import type { Alert } from "@/types"

const MAX_RETRIES = 10
const BASE_DELAY = 1000

export function createAlertsFeed(token: string) {
  let ws: WebSocket | null = null
  let retries = 0
  let heartbeatTimer: ReturnType<typeof setTimeout>

  function connect() {
    useAlertStore.getState().setWsStatus("reconnecting")
    const wsUrl = `${location.origin.replace("https", "wss").replace("http", "ws")}/api/ws/alerts?token=${token}`
    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      retries = 0
      useAlertStore.getState().setWsStatus("connected")
      scheduleHeartbeat()
    }

    ws.onmessage = (event) => {
      clearTimeout(heartbeatTimer)
      scheduleHeartbeat()
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === "new_alert") {
          const alert = msg.alert as Alert
          useAlertStore.getState().prependAlert(alert)
          if (alert.severity === "critical") {
            useUIStore.getState().addToast({
              type: "error",
              message: `Critical alert: ${alert.entity?.host ?? alert.entity?.source_ip ?? "unknown"}`,
            })
          }
        }
      } catch { /* ignore parse errors */ }
    }

    ws.onclose = () => {
      clearTimeout(heartbeatTimer)
      if (retries < MAX_RETRIES) {
        const delay = Math.min(BASE_DELAY * 2 ** retries, 30_000)
        retries++
        useAlertStore.getState().setWsStatus("reconnecting")
        setTimeout(connect, delay)
      } else {
        useAlertStore.getState().setWsStatus("disconnected")
      }
    }
  }

  function scheduleHeartbeat() {
    heartbeatTimer = setTimeout(() => { ws?.close() }, 40_000)
  }

  connect()
  return { disconnect: () => { retries = MAX_RETRIES; ws?.close() } }
}
