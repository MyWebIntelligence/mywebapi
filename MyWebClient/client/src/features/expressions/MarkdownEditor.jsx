import { useState } from 'react'
import { Row, Col, Button } from 'react-bootstrap'
import ReactMarkdown from 'react-markdown'
import TextareaAutosize from 'react-textarea-autosize'

/**
 * Editeur Markdown avec vue partagee (edition + apercu en direct).
 *
 * Props:
 *   content   - chaine markdown a afficher / editer
 *   onChange  - callback(newContent) quand le texte change
 *   readOnly  - si true, pas de bouton d'edition
 */
export default function MarkdownEditor({ content = '', onChange, readOnly = false }) {
  const [editing, setEditing] = useState(false)

  const handleChange = (e) => {
    if (onChange) {
      onChange(e.target.value)
    }
  }

  const isEmpty = !content || content.trim() === ''

  return (
    <div className="markdown-editor">
      {/* Toolbar */}
      {!readOnly && (
        <div className="mb-2">
          <Button
            size="sm"
            variant={editing ? 'primary' : 'outline-primary'}
            onClick={() => setEditing(!editing)}
          >
            <i className={`fas fa-${editing ? 'eye' : 'pen'} me-1`} />
            {editing ? 'Apercu' : 'Editer'}
          </Button>
        </div>
      )}

      {/* View mode */}
      {!editing ? (
        <div
          className="markdown-editor-content border rounded p-3"
          style={{ minHeight: 120, borderColor: '#ccc' }}
        >
          {isEmpty ? (
            <span className="text-muted fst-italic">Aucun contenu</span>
          ) : (
            <ReactMarkdown>{content}</ReactMarkdown>
          )}
        </div>
      ) : (
        /* Edit mode: side-by-side */
        <Row>
          <Col md={6}>
            <div className="mb-1">
              <small className="text-muted fw-bold">Markdown</small>
            </div>
            <TextareaAutosize
              className="form-control font-monospace small"
              style={{
                minHeight: 200,
                borderColor: '#ccc',
                resize: 'vertical',
              }}
              value={content}
              onChange={handleChange}
              minRows={8}
              placeholder="Saisissez votre contenu en Markdown..."
            />
          </Col>
          <Col md={6}>
            <div className="mb-1">
              <small className="text-muted fw-bold">Apercu</small>
            </div>
            <div
              className="markdown-editor-content border rounded p-3"
              style={{ minHeight: 200, borderColor: '#ccc', overflowY: 'auto' }}
            >
              {isEmpty ? (
                <span className="text-muted fst-italic">Aucun contenu</span>
              ) : (
                <ReactMarkdown>{content}</ReactMarkdown>
              )}
            </div>
          </Col>
        </Row>
      )}
    </div>
  )
}
