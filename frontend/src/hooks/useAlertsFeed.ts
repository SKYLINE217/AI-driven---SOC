/**
 * useAlertsFeed — Live WebSocket hook for the alert feed.
 *
 * Connects to /ws/alerts (proxied to FastAPI by Vite in dev, BFF in prod).
 * On connect: receives initial_state with all current alerts.
 * On message: prepends new alerts with a highlight animation.
 * Auto-reconnects with exponential backoff (1s, 2s, 4s, 8s, cap 30s).
 *
 * Must be called once at the Alert Queue page level.
 */

import { useEffect, useRef, useCallback } from 'react';
import { useAlertStore } from '../stores/alertStore';
import type { Alert } from '../types';

const WS_URL = '/ws/alerts';
const MAX_BACKOFF_MS = 30_000;

export function useAlertsFeed() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const backoffMs = useRef(1000);
  const mountedRef = useRef(true);

  const { setAlerts, prependAlert, setWsStatus } = useAlertStore();

  const connect = useCallback(() => {
    if (!mountedRef.current) return;

    // Determine full WS URL: in dev Vite proxies /ws → ws://localhost:8000
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}${WS_URL}`;

    setWsStatus('reconnecting');
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) { ws.close(); return; }
      setWsStatus('connected');
      backoffMs.current = 1000; // reset backoff on successful connect
    };

    ws.onmessage = (event: MessageEvent) => {
      if (!mountedRef.current) return;
      try {
        const msg = JSON.parse(event.data as string);

        if (msg.type === 'initial_state' && Array.isArray(msg.alerts)) {
          // Full initial state — replace the store
          setAlerts(msg.alerts as Alert[]);
        } else if (msg.type === 'new_alert' && msg.alert) {
          // New alert broadcast — prepend with animation
          prependAlert(msg.alert as Alert);
        }
        // msg.type === 'ping' — ignore (just a keep-alive)
      } catch {
        // Malformed JSON — ignore
      }
    };

    ws.onerror = () => {
      ws.close();
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      setWsStatus('disconnected');
      wsRef.current = null;

      // Schedule reconnect with exponential backoff
      const delay = backoffMs.current;
      backoffMs.current = Math.min(backoffMs.current * 2, MAX_BACKOFF_MS);
      reconnectTimerRef.current = setTimeout(connect, delay);
    };
  }, [setAlerts, prependAlert, setWsStatus]);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      wsRef.current?.close();
      setWsStatus('disconnected');
    };
  }, [connect, setWsStatus]);
}
