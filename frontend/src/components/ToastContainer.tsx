import { useEffect } from 'react'
import { useUIStore } from '@/stores/uiStore'
import { X } from 'lucide-react'

export function ToastContainer() {
  const toasts = useUIStore((s) => s.toasts)
  const removeToast = useUIStore((s) => s.removeToast)

  useEffect(() => {
    const timers: ReturnType<typeof setTimeout>[] = []
    toasts.forEach((toast) => {
      const delay = toast.type === 'error' ? 8000 : 6000
      timers.push(setTimeout(() => removeToast(toast.id), delay))
    })
    return () => timers.forEach(clearTimeout)
  }, [toasts, removeToast])

  if (toasts.length === 0) return null

  return (
    <div className="toast-container" aria-live="polite">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast toast-${toast.type}`} role="alert">
          <span style={{ flex: 1 }}>{toast.message}</span>
          <button
            onClick={() => removeToast(toast.id)}
            style={{
              background: 'none',
              border: 'none',
              color: 'inherit',
              cursor: 'pointer',
              padding: '2px',
              opacity: 0.7,
            }}
            aria-label="Dismiss"
          >
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  )
}
