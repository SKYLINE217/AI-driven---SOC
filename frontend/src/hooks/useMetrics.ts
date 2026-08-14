import { useMemo } from "react"
import { genThroughput, genAlertVolume, genLatency, generateScoreDistribution } from "@/data/generators"

export function useMetrics() {
  const data = useMemo(() => ({
    throughput: genThroughput(),
    alertVolume: genAlertVolume(),
    latency: genLatency(),
    scoreDistribution: generateScoreDistribution(),
    eventsPerSec: 213,
    llmCostPer1k: 0.042,
    p50Latency: 1.85,
  }), [])
  return { data, isLoading: false }
}
