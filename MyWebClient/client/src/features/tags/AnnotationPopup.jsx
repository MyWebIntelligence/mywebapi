import { useEffect, useRef } from 'react'

/**
 * AnnotationPopup
 *
 * Floating popup displayed after text selection that lets the user pick a tag
 * for annotating the selected span.
 *
 * Props:
 *   position  - { x: number, y: number } viewport coordinates
 *   tags      - array of { id, name, color }
 *   onSelect  - (tagId) => void
 *   onClose   - () => void
 */
export default function AnnotationPopup({ position, tags = [], onSelect, onClose }) {
  const ref = useRef(null)

  /* Close on click outside */
  useEffect(() => {
    function handleClickOutside(e) {
      if (ref.current && !ref.current.contains(e.target)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [onClose])

  /* Close on Escape */
  useEffect(() => {
    function handleKey(e) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [onClose])

  if (!position) return null

  return (
    <div
      ref={ref}
      className="tagging-popup"
      style={{ left: position.x, top: position.y }}
    >
      <div style={{ fontWeight: 600, marginBottom: 4, fontSize: '0.85rem' }}>
        Annoter avec :
      </div>

      <ul style={{ listStyle: 'none', margin: 0, padding: 0, maxHeight: 200, overflowY: 'auto' }}>
        {tags.map((tag) => (
          <li key={tag.id}>
            <button
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                width: '100%',
                background: 'none',
                border: 'none',
                padding: '4px 6px',
                cursor: 'pointer',
                borderRadius: 3,
                fontSize: '0.85rem',
                textAlign: 'left'
              }}
              onMouseOver={(e) => { e.currentTarget.style.background = '#f0f4ff' }}
              onMouseOut={(e) => { e.currentTarget.style.background = 'none' }}
              onClick={() => onSelect(tag.id)}
            >
              <span
                style={{
                  display: 'inline-block',
                  width: 10,
                  height: 10,
                  borderRadius: '50%',
                  backgroundColor: tag.color || '#007bff',
                  flexShrink: 0
                }}
              />
              {tag.name}
            </button>
          </li>
        ))}
      </ul>

      {tags.length === 0 && (
        <div style={{ color: '#888', fontSize: '0.8rem', padding: 4 }}>Aucun tag disponible</div>
      )}

      <div style={{ borderTop: '1px solid #eee', marginTop: 6, paddingTop: 6, textAlign: 'right' }}>
        <button
          style={{
            background: 'none',
            border: '1px solid #ccc',
            borderRadius: 3,
            padding: '2px 10px',
            cursor: 'pointer',
            fontSize: '0.8rem',
            color: '#555'
          }}
          onClick={onClose}
        >
          Annuler
        </button>
      </div>
    </div>
  )
}
