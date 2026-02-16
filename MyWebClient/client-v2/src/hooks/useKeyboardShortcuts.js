import { useEffect } from 'react'

/**
 * Register keyboard shortcuts that are ignored when focus is in a form element.
 * @param {Array<{key: string, action: Function}>} shortcuts
 * @param {Array} deps - Dependency array for useEffect
 */
export default function useKeyboardShortcuts(shortcuts, deps = []) {
  useEffect(() => {
    const handler = (e) => {
      // Ignore shortcuts when typing in form fields
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return
      if (e.target.isContentEditable) return

      const match = shortcuts.find((s) => {
        if (s.key !== e.key) return false
        if (s.ctrl && !e.ctrlKey && !e.metaKey) return false
        if (s.shift && !e.shiftKey) return false
        if (s.alt && !e.altKey) return false
        return true
      })

      if (match) {
        e.preventDefault()
        match.action()
      }
    }

    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
}
