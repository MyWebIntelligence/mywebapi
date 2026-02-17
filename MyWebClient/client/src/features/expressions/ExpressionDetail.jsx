import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Row, Col, Card, Badge, Button, Alert } from 'react-bootstrap'
import client from '../../api/client'
import * as api from '../../api/expressionsApi'
import * as ops from '../../api/operationsApi'
import * as tagsApi from '../../api/tagsApi'
import LoadingSpinner from '../../components/LoadingSpinner'
import ConfirmDialog from '../../components/ConfirmDialog'
import useKeyboardShortcuts from '../../hooks/useKeyboardShortcuts'
import MarkdownEditor from './MarkdownEditor'
import TextAnnotator from '../tags/TextAnnotator'

export default function ExpressionDetail() {
  const { landId, exprId } = useParams()
  const navigate = useNavigate()
  const [expr, setExpr] = useState(null)
  const [editing, setEditing] = useState(false)
  const [editContent, setEditContent] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [showDelete, setShowDelete] = useState(false)
  const [showDeleteMedia, setShowDeleteMedia] = useState(null)
  const [dirty, setDirty] = useState(false)
  const [message, setMessage] = useState(null)

  // Annotation state
  const [tags, setTags] = useState([])
  const [annotations, setAnnotations] = useState([])

  const fetchExpr = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.getExpression(exprId)
      setExpr(data)
      setEditContent(data.content || data.readable || '')
    } catch (err) {
      console.error('Failed to fetch expression:', err)
    } finally {
      setLoading(false)
    }
  }, [landId, exprId])

  // Fetch tags and annotations for this expression
  const fetchAnnotations = useCallback(async () => {
    try {
      const [tagsData, tcData] = await Promise.all([
        tagsApi.getTags(landId).catch(() => []),
        tagsApi.getExpressionTaggedContent(exprId).catch(() => []),
      ])
      setTags(Array.isArray(tagsData) ? tagsData : tagsData?.items || [])
      const items = Array.isArray(tcData) ? tcData : tcData?.items || []
      setAnnotations(
        items.map((tc) => ({
          id: tc.id,
          tag_id: tc.tag_id,
          tag_name: tc.tag_name || tc.tag?.name || '',
          tag_color: tc.tag_color || tc.tag?.color || '#007bff',
          from_char: tc.from_char ?? 0,
          to_char: tc.to_char ?? 0,
          text: tc.text || '',
        }))
      )
    } catch {
      // Non-blocking
    }
  }, [landId, exprId])

  useEffect(() => {
    fetchExpr()
    fetchAnnotations()
  }, [fetchExpr, fetchAnnotations])

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.updateExpression(exprId, { content: editContent })
      setDirty(false)
      setMessage({ type: 'success', text: 'Sauvegard\u00e9' })
      fetchExpr()
    } catch (err) {
      setMessage({ type: 'danger', text: err.response?.data?.detail || 'Erreur de sauvegarde' })
    } finally {
      setSaving(false)
    }
  }

  const handleReadable = async () => {
    setSaving(true)
    try {
      await ops.readable(landId, { limit: 1 })
      fetchExpr()
      setMessage({ type: 'success', text: 'Readabilize termin\u00e9' })
    } catch (err) {
      setMessage({ type: 'danger', text: 'Erreur readabilize' })
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    try {
      await api.deleteExpression(exprId)
      navigate(`/lands/${landId}/expressions`)
    } catch {}
  }

  const handleDeleteMedia = async (mediaId) => {
    try {
      // Attempt to delete media via API
      await client.delete(`/v2/media/${mediaId}`)
      setMessage({ type: 'success', text: 'Media supprim\u00e9' })
      fetchExpr()
    } catch {
      setMessage({ type: 'danger', text: 'Erreur suppression media' })
    } finally {
      setShowDeleteMedia(null)
    }
  }

  // Annotation handlers
  const handleAnnotate = async (tagId, fromChar, toChar, selectedText) => {
    try {
      await tagsApi.createTaggedContentV1({
        tag_id: tagId,
        expression_id: Number(exprId),
        from_char: fromChar,
        to_char: toChar,
        text: selectedText,
      })
      fetchAnnotations()
    } catch {
      setMessage({ type: 'danger', text: 'Erreur lors de l\'annotation' })
    }
  }

  const handleDeleteAnnotation = async (annotationId) => {
    try {
      await tagsApi.deleteTaggedContentV1(annotationId)
      fetchAnnotations()
    } catch {
      setMessage({ type: 'danger', text: 'Erreur suppression annotation' })
    }
  }

  const goToExpr = (delta) => {
    if (dirty) {
      if (!window.confirm('Modifications non sauvegard\u00e9es. Continuer ?')) return
    }
    const newId = Number(exprId) + delta
    if (newId > 0) navigate(`/lands/${landId}/expressions/${newId}`)
  }

  useKeyboardShortcuts([
    { key: 'Escape', action: () => navigate(`/lands/${landId}/expressions`) },
    { key: 'ArrowLeft', action: () => goToExpr(-1) },
    { key: 'ArrowRight', action: () => goToExpr(1) },
    { key: 'e', action: () => setEditing((e) => !e) },
    { key: 'r', action: handleReadable },
    { key: 's', action: () => dirty && handleSave() },
    { key: 'd', action: () => setShowDelete(true) },
  ], [exprId, dirty, editing])

  if (loading) return <LoadingSpinner />
  if (!expr) return <Alert variant="danger">Expression non trouv&eacute;e</Alert>

  return (
    <div>
      <div className="d-flex justify-content-between align-items-start mb-3">
        <div>
          <small className="App-objtype">Expression #{expr.id}</small>
          <h5>{expr.title || '(sans titre)'}</h5>
          {expr.url && (
            <a href={expr.url} target="_blank" rel="noopener noreferrer" className="App-link small">
              <i className="fas fa-external-link-alt me-1" />
              {expr.url}
            </a>
          )}
        </div>
        <div className="d-flex gap-1">
          <Button variant="outline-primary" size="sm" onClick={() => goToExpr(-1)} title="Pr\u00e9c\u00e9dente (←)">
            <i className="fas fa-chevron-left" />
          </Button>
          <Button variant="outline-primary" size="sm" onClick={() => goToExpr(1)} title="Suivante (→)">
            <i className="fas fa-chevron-right" />
          </Button>
        </div>
      </div>

      {message && (
        <Alert variant={message.type} dismissible onClose={() => setMessage(null)} className="py-1">
          {message.text}
        </Alert>
      )}

      <Row>
        {/* Left panel: content */}
        <Col md={8}>
          {expr.lead && <p className="lead">{expr.lead}</p>}

          <div className="mb-2 d-flex gap-1">
            <Button size="sm" variant={editing ? 'primary' : 'outline-primary'} onClick={() => setEditing(!editing)}>
              <i className={`fas fa-${editing ? 'eye' : 'pen'} me-1`} />
              {editing ? 'Voir' : '\u00c9diter'}
            </Button>
            <Button size="sm" variant="outline-secondary" onClick={handleReadable} disabled={saving}>
              <i className="fas fa-magic me-1" />
              Readabilize
            </Button>
            <Button size="sm" variant="outline-success" onClick={handleSave} disabled={!dirty || saving}>
              <i className="fas fa-save me-1" />
              Sauvegarder
            </Button>
            <Button size="sm" variant="outline-danger" onClick={() => setShowDelete(true)}>
              <i className="fas fa-trash me-1" />
              Supprimer
            </Button>
          </div>

          {editing ? (
            <MarkdownEditor
              content={editContent}
              onChange={(val) => {
                setEditContent(val)
                setDirty(true)
              }}
            />
          ) : (
            <TextAnnotator
              content={expr.content || expr.readable || '<em>Pas de contenu</em>'}
              annotations={annotations}
              tags={tags}
              onAnnotate={handleAnnotate}
              onDeleteAnnotation={handleDeleteAnnotation}
            />
          )}
        </Col>

        {/* Right panel: metadata + media */}
        <Col md={4}>
          <Card className="mb-3">
            <Card.Header>
              <i className="fas fa-info-circle me-2" />
              M&eacute;tadonn&eacute;es
            </Card.Header>
            <Card.Body className="small">
              <div><strong>ID:</strong> {expr.id}</div>
              <div>
                <strong>Relevance:</strong>{' '}
                <Badge bg="info">{expr.relevance ?? '\u2014'}</Badge>
              </div>
              <div><strong>Depth:</strong> {expr.depth ?? '\u2014'}</div>
              <div><strong>Quality:</strong> {expr.quality_score ?? '\u2014'}</div>
              <div>
                <strong>Sentiment:</strong>{' '}
                {expr.sentiment_score != null
                  ? Number(expr.sentiment_score).toFixed(2)
                  : '\u2014'}
              </div>
              <div><strong>Language:</strong> {expr.language ?? '\u2014'}</div>
              <div><strong>Domain:</strong> {expr.domain_name || expr.domain_id || '\u2014'}</div>
              {expr.seo_rank && (
                <div><strong>SEO Rank:</strong> {JSON.stringify(expr.seo_rank)}</div>
              )}
              {expr.valid_llm != null && (
                <div>
                  <strong>LLM Valid:</strong>{' '}
                  <Badge bg={expr.valid_llm ? 'success' : 'danger'}>
                    {expr.valid_llm ? 'Oui' : 'Non'}
                  </Badge>
                </div>
              )}
            </Card.Body>
          </Card>

          {/* Tags on this expression */}
          {annotations.length > 0 && (
            <Card className="mb-3">
              <Card.Header>
                <i className="fas fa-tags me-2" />
                Annotations ({annotations.length})
              </Card.Header>
              <Card.Body className="small">
                {annotations.map((a) => (
                  <div key={a.id} className="d-flex align-items-center gap-2 mb-1">
                    <span
                      style={{
                        display: 'inline-block',
                        width: 10,
                        height: 10,
                        borderRadius: '50%',
                        backgroundColor: a.tag_color || '#007bff',
                      }}
                    />
                    <span className="tagLabel">{a.tag_name}</span>
                    <span className="text-muted" style={{ fontSize: '0.8em' }}>
                      &ldquo;{(a.text || '').substring(0, 40)}{a.text?.length > 40 ? '...' : ''}&rdquo;
                    </span>
                  </div>
                ))}
              </Card.Body>
            </Card>
          )}

          {/* Media gallery with delete */}
          {expr.media && expr.media.length > 0 && (
            <Card>
              <Card.Header>
                <i className="fas fa-images me-2" />
                M&eacute;dias ({expr.media.length})
              </Card.Header>
              <Card.Body>
                {expr.media.map((m, i) => (
                  <div key={m.id || i} className="mb-2 position-relative">
                    <img
                      src={m.url}
                      alt={m.alt || ''}
                      className="img-fluid rounded"
                      style={{ maxHeight: 150 }}
                    />
                    <Button
                      size="sm"
                      variant="outline-danger"
                      className="position-absolute top-0 end-0 m-1"
                      style={{ padding: '1px 5px', fontSize: '0.7rem' }}
                      onClick={() => setShowDeleteMedia(m.id || i)}
                      title="Supprimer ce media"
                    >
                      <i className="fas fa-times" />
                    </Button>
                  </div>
                ))}
              </Card.Body>
            </Card>
          )}
        </Col>
      </Row>

      <ConfirmDialog
        show={showDelete}
        title="Supprimer l'expression"
        message="Voulez-vous supprimer cette expression ?"
        onConfirm={handleDelete}
        onCancel={() => setShowDelete(false)}
      />

      <ConfirmDialog
        show={showDeleteMedia != null}
        title="Supprimer le media"
        message="Voulez-vous supprimer ce media ?"
        onConfirm={() => handleDeleteMedia(showDeleteMedia)}
        onCancel={() => setShowDeleteMedia(null)}
      />
    </div>
  )
}
