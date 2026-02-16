import { useState, useCallback } from 'react'

let idCounter = 0

/**
 * Toast notification hook.
 * @returns {{ toasts, addToast, removeToast }}
 */
export default function useToast() {
  const [toasts, setToasts] = useState([])

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const addToast = useCallback(
    (message, variant = 'info', autoDismiss = 5000) => {
      const id = ++idCounter
      setToasts((prev) => [...prev, { id, message, variant }])
      if (autoDismiss > 0) {
        setTimeout(() => removeToast(id), autoDismiss)
      }
      return id
    },
    [removeToast]
  )

  return { toasts, addToast, removeToast }
}
