import { useMemo } from "react"
import { REAL_INCIDENTS } from "@/data/seedIncidents"
import type { Incident } from "@/types"

export function useIncidentDetail(id: string | undefined) {
  const incident = useMemo<Incident | null>(
    () => REAL_INCIDENTS.find((i) => i.id === id) ?? null,
    [id]
  )
  return { incident, isLoading: false }
}
