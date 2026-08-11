/**
 * useAlertsFeed — live WebSocket connection to /ws/alerts
 * On mount: establishes authenticated WS, subscribes to new alerts.
 * Falls back gracefully to disconnected state on error.
 */

import { useEffect, useRef, useCallback } from 'react'
import { useAlertStore } from '@/stores/alertStore'
import { useAuthStore } from '@/stores/authStore'
import type { Alert } from '@/types'

const WS_BASE =
  typeof window !== 'undefined' && window.location.hostname !== 'localhost'
    ? `wss://${window.location.host}`
    : 'ws://localhost:8000'

const RECONNECT_DELAY_MS = 3000
const MAX_RECONNECT_ATTEMPTS = 10

export function useAlertsFeed() {
  const wsRef = useRef<WebSocket | null>(null)
  const attemptsRef = useRef(0)
  const unmountedRef = useRef(false)

  const token = useAuthStore((s) => s.token)
  const setWsStatus = useAlertStore((s) => s.setWsStatus)
  const prependAlert = useAlertStore((s) => s.prependAlert)

  const connect = useCallback(() => {
    if (unmountedRef.current) return

    // Don't connect without auth token
    if (!token) {
      setWsStatus('disconnected')
      return
    }

    setWsStatus('reconnecting')
    const url = `${WS_BASE}/ws/alerts?token=${encodeURIComponent(token)}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      attemptsRef.current = 0
      setWsStatus('connected')
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as {
          type: string
          payload?: Alert
        }
        if (msg.type === 'new_alert' && msg.payload) {
          prependAlert(msg.payload)
        }
      } catch {
        // ignore malformed messages
      }
    }

    ws.onerror = () => {
      setWsStatus('reconnecting')
    }

    ws.onclose = () => {
      if (unmountedRef.current) return
      setWsStatus('disconnected')
      if (attemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
        attemptsRef.current += 1
        const delay =
          RECONNECT_DELAY_MS * Math.min(attemptsRef.current, 5)
        setTimeout(connect, delay)
      }
    }
  }, [token, setWsStatus, prependAlert])

  useEffect(() => {
    unmountedRef.current = false
    connect()
    return () => {
      unmountedRef.current = true
      wsRef.current?.close()
    }
  }, [connect])
}
