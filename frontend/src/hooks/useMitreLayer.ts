import { useMemo } from "react"
import { REAL_INCIDENTS } from "@/data/seedIncidents"

export function useMitreLayer() {
  const layer = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const inc of REAL_INCIDENTS) {
      const t = inc.technique.split(".")[0]
      counts[t] = (counts[t] ?? 0) + 1
    }
    return counts
  }, [])
  return { layer, isLoading: false }
}
