import { useState, useRef, useCallback, useMemo } from 'react'
import AnnotationPopup from './AnnotationPopup'

/**
 * TextAnnotator
 *
 * Renders HTML content with highlighted annotation spans and allows users to
 * select text and tag it via a floating popup.
 *
 * Props:
 *   content            - HTML string to display
 *   annotations        - Array of { id, tag_id, tag_name, tag_color, from_char, to_char, text }
 *   tags               - Available tags for annotation (array of { id, name, color })
 *   onAnnotate         - (tagId, fromChar, toChar, text) => void
 *   onDeleteAnnotation - (annotationId) => void
 */

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

/**
 * Strip HTML tags to produce plain text (used for char offset calculation).
 */
function stripHtml(html) {
  const tmp = document.createElement('div')
  tmp.innerHTML = html
  return tmp.textContent || tmp.innerText || ''
}

/**
 * Build rendered segments from plain text + annotation ranges.
 * Handles overlapping annotations by splitting the text into non-overlapping
 * segments, each carrying the list of annotations that cover it.
 */
function buildSegments(plainText, annotations) {
  if (!annotations || annotations.length === 0) {
    return [{ start: 0, end: plainText.length, text: plainText, annotations: [] }]
  }

  // Collect all boundary points
  const points = new Set([0, plainText.length])
  annotations.forEach((a) => {
    const from = Math.max(0, a.from_char)
    const to = Math.min(plainText.length, a.to_char)
    points.add(from)
    points.add(to)
  })

  const sorted = Array.from(points).sort((a, b) => a - b)
  const segments = []

  for (let i = 0; i < sorted.length - 1; i++) {
    const start = sorted[i]
    const end = sorted[i + 1]
    const covering = annotations.filter(
      (a) => a.from_char <= start && a.to_char >= end
    )
    segments.push({
      start,
      end,
      text: plainText.slice(start, end),
      annotations: covering
    })
  }

  return segments
}

/**
 * Blend a hex colour to 30% opacity against white.
 */
function colorAt30(hex) {
  if (!hex) return 'rgba(0,123,255,0.3)'
  const clean = hex.replace('#', '')
  const r = parseInt(clean.substring(0, 2), 16)
  const g = parseInt(clean.substring(2, 4), 16)
  const b = parseInt(clean.substring(4, 6), 16)
  return `rgba(${r},${g},${b},0.3)`
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function TextAnnotator({
  content = '',
  annotations = [],
  tags = [],
  onAnnotate,
  onDeleteAnnotation
}) {
  const containerRef = useRef(null)
  const [popup, setPopup] = useState(null) // { x, y, fromChar, toChar, selectedText }

  const plainText = useMemo(() => stripHtml(content), [content])
  const segments = useMemo(() => buildSegments(plainText, annotations), [plainText, annotations])

  /* ------ Selection handler ------ */
  const handleMouseUp = useCallback(() => {
    const sel = window.getSelection()
    if (!sel || sel.isCollapsed || !containerRef.current) return

    const range = sel.getRangeAt(0)
    if (!containerRef.current.contains(range.commonAncestorContainer)) return

    const selectedText = sel.toString()
    if (!selectedText.trim()) return

    // Walk text nodes inside container to compute char offsets
    const walker = document.createTreeWalker(containerRef.current, NodeFilter.SHOW_TEXT, null)
    let charOffset = 0
    let fromChar = null
    let toChar = null

    while (walker.nextNode()) {
      const node = walker.currentNode
      const nodeLen = node.textContent.length

      // Determine start offset
      if (fromChar === null && range.startContainer === node) {
        fromChar = charOffset + range.startOffset
      } else if (fromChar === null && node.compareDocumentPosition(range.startContainer) & Node.DOCUMENT_POSITION_FOLLOWING) {
        // range.startContainer comes after this node, keep walking
      } else if (fromChar === null && range.startContainer === containerRef.current) {
        fromChar = charOffset
      }

      // Determine end offset
      if (range.endContainer === node) {
        toChar = charOffset + range.endOffset
        break
      }

      charOffset += nodeLen
    }

    if (fromChar === null || toChar === null || fromChar === toChar) return

    // Position the popup near the end of the selection
    const rect = range.getBoundingClientRect()
    setPopup({
      x: rect.right + 4,
      y: rect.top,
      fromChar,
      toChar,
      selectedText
    })

    // Don't clear selection yet -- user still sees it highlighted
  }, [])

  /* ------ Tag selected from popup ------ */
  const handleTagSelect = useCallback(
    (tagId) => {
      if (popup && onAnnotate) {
        onAnnotate(tagId, popup.fromChar, popup.toChar, popup.selectedText)
      }
      setPopup(null)
      window.getSelection()?.removeAllRanges()
    },
    [popup, onAnnotate]
  )

  const handlePopupClose = useCallback(() => {
    setPopup(null)
    window.getSelection()?.removeAllRanges()
  }, [])

  /* ------ Render ------ */
  return (
    <div style={{ position: 'relative' }}>
      <div
        ref={containerRef}
        onMouseUp={handleMouseUp}
        style={{
          lineHeight: 1.7,
          fontSize: '0.95rem',
          border: '1px solid #ccc',
          borderRadius: 4,
          padding: 12,
          minHeight: 80,
          userSelect: 'text'
        }}
      >
        {segments.map((seg, idx) => {
          if (seg.annotations.length === 0) {
            return <span key={idx}>{seg.text}</span>
          }

          // Use the colour of the first (outermost) annotation
          const primary = seg.annotations[0]
          const bg = colorAt30(primary.tag_color)
          const title = seg.annotations.map((a) => a.tag_name).join(', ')

          return (
            <span
              key={idx}
              className="annotation-highlight"
              style={{ backgroundColor: bg }}
              title={title}
              onClick={() => {
                if (seg.annotations.length === 1 && onDeleteAnnotation) {
                  if (window.confirm(`Supprimer l'annotation "${primary.tag_name}" ?`)) {
                    onDeleteAnnotation(primary.id)
                  }
                }
              }}
            >
              {seg.text}
            </span>
          )
        })}
      </div>

      {/* Floating tag selector */}
      {popup && (
        <AnnotationPopup
          position={{ x: popup.x, y: popup.y }}
          tags={tags}
          onSelect={handleTagSelect}
          onClose={handlePopupClose}
        />
      )}
    </div>
  )
}
