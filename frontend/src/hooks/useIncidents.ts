import { useMemo } from "react"
import { REAL_INCIDENTS } from "@/data/seedIncidents"
import type { Incident } from "@/types"

export function useIncidents() {
  const incidents = useMemo<Incident[]>(() => REAL_INCIDENTS, [])
  return { incidents, isLoading: false, error: null }
}
