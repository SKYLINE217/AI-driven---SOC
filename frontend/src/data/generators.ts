import type { MetricPoint, LatencyPoint, ScoreBin } from "@/types"

const now = Date.now()

export function genThroughput(): MetricPoint[] {
  return Array.from({ length: 60 }, (_, i) => ({
    t: new Date(now - (59 - i) * 60_000).toISOString().substring(11, 16),
    value: Math.round(180 + 40 * Math.sin(i / 10) + Math.random() * 20),
  }))
}

export function genAlertVolume(): MetricPoint[] {
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
  const base = [1240, 1580, 2100, 1870, 2340, 890, 640]
  return days.map((t, i) => ({ t, value: base[i] + Math.floor(Math.random() * 200 - 100) }))
}

export function genLatency(): LatencyPoint[] {
  return Array.from({ length: 30 }, (_, i) => ({
    t: new Date(now - (29 - i) * 60_000).toISOString().substring(11, 16),
    p50: +(1.6 + Math.random() * 0.8).toFixed(2),
    p95: +(3.8 + Math.random() * 1.2).toFixed(2),
  }))
}

export function generateScoreDistribution(): ScoreBin[] {
  const bins = [
    { label: "0.64–0.67", count: 312 },
    { label: "0.67–0.70", count: 489 },
    { label: "0.70–0.73", count: 721 },
    { label: "0.73–0.76", count: 834 },
    { label: "0.76–0.79", count: 693 },
    { label: "0.79–0.82", count: 541 },
    { label: "0.82–0.85", count: 398 },
    { label: "0.85–0.88", count: 287 },
    { label: "0.88–0.91", count: 156 },
    { label: "0.91+",     count: 69  },
  ]
  return bins.map((b) => ({ ...b, count: b.count + Math.floor(Math.random() * 40 - 20) }))
}
