import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { Row, Col, Button, Form, Card, ListGroup, Badge, Alert } from 'react-bootstrap'
import * as tagsApi from '../../api/tagsApi'
import LoadingSpinner from '../../components/LoadingSpinner'
import ConfirmDialog from '../../components/ConfirmDialog'

export default function TagManager() {
  const { landId } = useParams()
  const [tags, setTags] = useState([])
  const [loading, setLoading] = useState(true)
  const [editTag, setEditTag] = useState(null)
  const [newName, setNewName] = useState('')
  const [newColor, setNewColor] = useState('#007bff')
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [error, setError] = useState(null)

  const fetchTags = async () => {
    setLoading(true)
    try {
      const data = await tagsApi.getTags(landId)
      setTags(Array.isArray(data) ? data : data.items || [])
    } catch {
      setTags([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTags()
  }, [landId])

  const handleCreate = async () => {
    if (!newName.trim()) return
    try {
      await tagsApi.createTag(landId, { name: newName, color: newColor })
      setNewName('')
      setNewColor('#007bff')
      fetchTags()
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur')
    }
  }

  const handleUpdate = async () => {
    if (!editTag) return
    try {
      await tagsApi.updateTag(editTag.id, { name: editTag.name, color: editTag.color })
      setEditTag(null)
      fetchTags()
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur')
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    try {
      await tagsApi.deleteTag(deleteTarget.id)
      setDeleteTarget(null)
      fetchTags()
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur')
    }
  }

  if (loading) return <LoadingSpinner />

  return (
    <div>
      <h4 className="mb-3">Tags - Land #{landId}</h4>

      {error && <Alert variant="danger" dismissible onClose={() => setError(null)}>{error}</Alert>}

      <Row className="g-3">
        <Col md={4}>
          <Card>
            <Card.Header>Nouveau tag</Card.Header>
            <Card.Body>
              <Form.Group className="mb-2">
                <Form.Control
                  size="sm"
                  placeholder="Nom du tag"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                />
              </Form.Group>
              <Form.Group className="mb-2">
                <Form.Label className="small">Couleur</Form.Label>
                <Form.Control
                  type="color"
                  size="sm"
                  value={newColor}
                  onChange={(e) => setNewColor(e.target.value)}
                />
              </Form.Group>
              <Button size="sm" variant="primary" onClick={handleCreate} disabled={!newName.trim()}>
                Cr&eacute;er
              </Button>
            </Card.Body>
          </Card>

          {editTag && (
            <Card className="mt-3">
              <Card.Header>Modifier le tag</Card.Header>
              <Card.Body>
                <Form.Group className="mb-2">
                  <Form.Control
                    size="sm"
                    value={editTag.name}
                    onChange={(e) => setEditTag({ ...editTag, name: e.target.value })}
                  />
                </Form.Group>
                <Form.Group className="mb-2">
                  <Form.Control
                    type="color"
                    size="sm"
                    value={editTag.color || '#007bff'}
                    onChange={(e) => setEditTag({ ...editTag, color: e.target.value })}
                  />
                </Form.Group>
                <div className="d-flex gap-1">
                  <Button size="sm" variant="primary" onClick={handleUpdate}>Enregistrer</Button>
                  <Button size="sm" variant="secondary" onClick={() => setEditTag(null)}>Annuler</Button>
                </div>
              </Card.Body>
            </Card>
          )}
        </Col>

        <Col md={8}>
          <Card>
            <Card.Header>Tags ({tags.length})</Card.Header>
            <ListGroup variant="flush">
              {tags.length === 0 ? (
                <ListGroup.Item className="text-muted">Aucun tag</ListGroup.Item>
              ) : (
                tags.map((tag) => (
                  <ListGroup.Item key={tag.id} className="d-flex justify-content-between align-items-center">
                    <div>
                      <Badge style={{ backgroundColor: tag.color || '#007bff' }} className="me-2">
                        &nbsp;
                      </Badge>
                      {tag.name}
                    </div>
                    <div className="d-flex gap-1">
                      <Button variant="outline-secondary" size="sm" onClick={() => setEditTag({ ...tag })}>
                        Modifier
                      </Button>
                      <Button variant="outline-danger" size="sm" onClick={() => setDeleteTarget(tag)}>
                        Supprimer
                      </Button>
                    </div>
                  </ListGroup.Item>
                ))
              )}
            </ListGroup>
          </Card>
        </Col>
      </Row>

      <ConfirmDialog
        show={!!deleteTarget}
        title="Supprimer le tag"
        message={`Supprimer le tag "${deleteTarget?.name}" ?`}
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}
