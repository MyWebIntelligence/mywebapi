import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Row, Col, Card, Badge, Button, Form, Alert } from 'react-bootstrap'
import * as api from '../../api/expressionsApi'
import * as ops from '../../api/operationsApi'
import LoadingSpinner from '../../components/LoadingSpinner'
import ConfirmDialog from '../../components/ConfirmDialog'
import useKeyboardShortcuts from '../../hooks/useKeyboardShortcuts'

export default function ExpressionDetail() {
  const { landId, exprId } = useParams()
  const navigate = useNavigate()
  const [expr, setExpr] = useState(null)
  const [editing, setEditing] = useState(false)
  const [editContent, setEditContent] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [showDelete, setShowDelete] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [message, setMessage] = useState(null)

  const fetchExpr = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.getExpression(landId, exprId)
      setExpr(data)
      setEditContent(data.content || data.readable || '')
    } catch (err) {
      console.error('Failed to fetch expression:', err)
    } finally {
      setLoading(false)
    }
  }, [landId, exprId])

  useEffect(() => {
    fetchExpr()
  }, [fetchExpr])

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.updateExpression(landId, exprId, { content: editContent })
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
      await api.deleteExpression(landId, exprId)
      navigate(`/lands/${landId}/expressions`)
    } catch {}
  }

  const goToExpr = (delta) => {
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
            <a href={expr.url} target="_blank" rel="noopener noreferrer" className="small">
              {expr.url}
            </a>
          )}
        </div>
        <div className="d-flex gap-1">
          <Button variant="outline-primary" size="sm" onClick={() => goToExpr(-1)}>&larr;</Button>
          <Button variant="outline-primary" size="sm" onClick={() => goToExpr(1)}>&rarr;</Button>
        </div>
      </div>

      {message && (
        <Alert variant={message.type} dismissible onClose={() => setMessage(null)} className="py-1">
          {message.text}
        </Alert>
      )}

      <Row>
        <Col md={8}>
          {expr.lead && <p className="lead">{expr.lead}</p>}

          <div className="mb-2 d-flex gap-1">
            <Button size="sm" variant={editing ? 'primary' : 'outline-primary'} onClick={() => setEditing(!editing)}>
              {editing ? 'Voir' : '&Eacute;diter'}
            </Button>
            <Button size="sm" variant="outline-secondary" onClick={handleReadable} disabled={saving}>
              Readabilize
            </Button>
            <Button size="sm" variant="outline-success" onClick={handleSave} disabled={!dirty || saving}>
              Sauvegarder
            </Button>
            <Button size="sm" variant="outline-danger" onClick={() => setShowDelete(true)}>
              Supprimer
            </Button>
          </div>

          {editing ? (
            <Form.Control
              as="textarea"
              rows={20}
              value={editContent}
              onChange={(e) => {
                setEditContent(e.target.value)
                setDirty(true)
              }}
              className="font-monospace small"
            />
          ) : (
            <div
              className="border rounded p-3"
              dangerouslySetInnerHTML={{ __html: expr.content || expr.readable || '<em>Pas de contenu</em>' }}
            />
          )}
        </Col>

        <Col md={4}>
          <Card className="mb-3">
            <Card.Header>M&eacute;tadonn&eacute;es</Card.Header>
            <Card.Body className="small">
              <div><strong>ID:</strong> {expr.id}</div>
              <div><strong>Relevance:</strong> <Badge bg="info">{expr.relevance ?? '—'}</Badge></div>
              <div><strong>Depth:</strong> {expr.depth ?? '—'}</div>
              <div><strong>Quality:</strong> {expr.quality_score ?? '—'}</div>
              <div><strong>Sentiment:</strong> {expr.sentiment_score ?? '—'}</div>
              <div><strong>Language:</strong> {expr.language ?? '—'}</div>
              <div><strong>Domain:</strong> {expr.domain_name || expr.domain_id || '—'}</div>
            </Card.Body>
          </Card>

          {expr.media && expr.media.length > 0 && (
            <Card>
              <Card.Header>M&eacute;dias ({expr.media.length})</Card.Header>
              <Card.Body>
                {expr.media.map((m, i) => (
                  <div key={i} className="mb-2">
                    <img
                      src={m.url}
                      alt={m.alt || ''}
                      className="img-fluid rounded"
                      style={{ maxHeight: 150 }}
                    />
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
    </div>
  )
}
