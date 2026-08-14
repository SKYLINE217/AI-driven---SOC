import { useEffect } from "react"
import { useAlertStore } from "@/stores/alertStore"
import { useUIStore } from "@/stores/uiStore"
import type { Alert, Severity } from "@/types"

const ENTITIES = ["10.0.3.99", "192.168.1.45", "svc-api", "dave", "172.16.5.22", "prod-db-03", "admin"]
const TECHNIQUES = ["T1110.001", "T1021.004", "T1041", "T1498", "T1046", "T1078"]
const SOURCES = ["syslog", "cloudtrail", "auth", "cicids"]

function makeAlert(): Alert {
  const score = 0.64 + Math.random() * 0.35
  const sev: Severity = score > 0.85 ? "critical" : score > 0.70 ? "high" : "medium"
  const entity = ENTITIES[Math.floor(Math.random() * ENTITIES.length)]
  return {
    id: crypto.randomUUID(),
    severity: sev,
    timestamp: new Date().toISOString(),
    entity: { source_ip: entity },
    technique_id: TECHNIQUES[Math.floor(Math.random() * TECHNIQUES.length)],
    technique_name: "Unknown",
    tactic: "Unknown",
    anomaly_score: +score.toFixed(3),
    status: "new",
    source_type: SOURCES[Math.floor(Math.random() * SOURCES.length)],
    created_at: new Date().toISOString(),
  }
}

export function useAlertsFeed() {
  const { prependAlert } = useAlertStore()
  const { addToast } = useUIStore()

  useEffect(() => {
    useAlertStore.getState().setWsStatus("connected")
    const id = setInterval(() => {
      const alert = makeAlert()
      prependAlert(alert)
      if (alert.severity === "critical") {
        addToast({ type: "error", message: `Critical alert: ${alert.entity.source_ip}` })
      }
    }, 4500)
    return () => {
      clearInterval(id)
      useAlertStore.getState().setWsStatus("disconnected")
    }
  }, [prependAlert, addToast])
}
