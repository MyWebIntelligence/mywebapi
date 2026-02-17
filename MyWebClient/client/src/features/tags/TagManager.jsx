import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { Row, Col, Button, Form, Card, Alert, Badge } from 'react-bootstrap'
import * as tagsApi from '../../api/tagsApi'
import LoadingSpinner from '../../components/LoadingSpinner'
import ConfirmDialog from '../../components/ConfirmDialog'
import TagTree from './TagTree'

export default function TagManager() {
  const { landId } = useParams()

  /* ---- state ---- */
  const [tags, setTags] = useState([])
  const [loading, setLoading] = useState(true)
  const [editTag, setEditTag] = useState(null)
  const [newName, setNewName] = useState('')
  const [newColor, setNewColor] = useState('#007bff')
  const [parentId, setParentId] = useState(null) // for "add child"
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [error, setError] = useState(null)
  const [showTaggedContent, setShowTaggedContent] = useState(false)
  const [taggedContent, setTaggedContent] = useState([])
  const [loadingContent, setLoadingContent] = useState(false)

  /* ---- fetch helpers ---- */
  const fetchTags = useCallback(async () => {
    setLoading(true)
    try {
      const data = await tagsApi.getTags(landId)
      setTags(Array.isArray(data) ? data : data.items || [])
    } catch {
      setTags([])
    } finally {
      setLoading(false)
    }
  }, [landId])

  useEffect(() => {
    fetchTags()
  }, [fetchTags])

  const fetchTaggedContent = useCallback(async () => {
    setLoadingContent(true)
    try {
      const data = await tagsApi.getTaggedContent({ land_id: landId })
      setTaggedContent(Array.isArray(data) ? data : data.items || [])
    } catch {
      setTaggedContent([])
    } finally {
      setLoadingContent(false)
    }
  }, [landId])

  /* ---- CRUD ---- */
  const handleCreate = async () => {
    if (!newName.trim()) return
    try {
      const payload = { name: newName, color: newColor }
      if (parentId) payload.parent_id = parentId
      await tagsApi.createTag(landId, payload)
      setNewName('')
      setNewColor('#007bff')
      setParentId(null)
      fetchTags()
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur lors de la creation')
    }
  }

  const handleUpdate = async () => {
    if (!editTag) return
    try {
      await tagsApi.updateTag(editTag.id, {
        name: editTag.name,
        color: editTag.color,
        parent_id: editTag.parent_id ?? null
      })
      setEditTag(null)
      fetchTags()
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur lors de la mise a jour')
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    try {
      await tagsApi.deleteTag(deleteTarget)
      setDeleteTarget(null)
      fetchTags()
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur lors de la suppression')
    }
  }

  /* ---- drag-drop reorder ---- */
  const handleReorder = useCallback(
    async (newTags) => {
      setTags(newTags)
      // Persist each tag's parent_id + position
      try {
        await Promise.all(
          newTags.map((t) =>
            tagsApi.updateTag(t.id, {
              name: t.name,
              color: t.color,
              parent_id: t.parent_id ?? null,
              position: t.position
            })
          )
        )
      } catch (err) {
        setError(err.response?.data?.detail || 'Erreur lors du reordonnancement')
        fetchTags() // rollback to server state
      }
    },
    [fetchTags]
  )

  /* ---- tree callbacks ---- */
  const handleAddChild = useCallback((pid) => {
    setParentId(pid)
    setEditTag(null)
    setNewName('')
    setNewColor('#007bff')
  }, [])

  const handleEdit = useCallback((tag) => {
    setEditTag({ ...tag })
    setParentId(null)
  }, [])

  const handleDeleteRequest = useCallback((tagId) => {
    setDeleteTarget(tagId)
  }, [])

  /* ---- tagged content overlay ---- */
  const handleShowTaggedContent = () => {
    setShowTaggedContent(true)
    fetchTaggedContent()
  }

  /* ---- render ---- */
  if (loading) return <LoadingSpinner />

  const parentTag = parentId ? tags.find((t) => t.id === parentId) : null
  const deleteTagObj = deleteTarget ? tags.find((t) => t.id === deleteTarget) : null

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h4 className="mb-0">Tags - Land #{landId}</h4>
        <Button variant="outline-primary" size="sm" onClick={handleShowTaggedContent}>
          <i className="fas fa-tags me-1" />
          Voir le contenu tagge
        </Button>
      </div>

      {error && (
        <Alert variant="danger" dismissible onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Row className="g-3">
        {/* ---- Left column: form ---- */}
        <Col md={4}>
          <Card>
            <Card.Header>
              {editTag
                ? 'Modifier le tag'
                : parentTag
                  ? `Nouveau sous-tag de "${parentTag.name}"`
                  : 'Nouveau tag'}
            </Card.Header>
            <Card.Body>
              {editTag ? (
                <>
                  <Form.Group className="mb-2">
                    <Form.Label className="small">Nom</Form.Label>
                    <Form.Control
                      size="sm"
                      value={editTag.name}
                      onChange={(e) => setEditTag({ ...editTag, name: e.target.value })}
                    />
                  </Form.Group>
                  <Form.Group className="mb-2">
                    <Form.Label className="small">Couleur</Form.Label>
                    <Form.Control
                      type="color"
                      size="sm"
                      value={editTag.color || '#007bff'}
                      onChange={(e) => setEditTag({ ...editTag, color: e.target.value })}
                    />
                  </Form.Group>
                  <div className="d-flex gap-1">
                    <Button size="sm" variant="primary" onClick={handleUpdate}>
                      Enregistrer
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => setEditTag(null)}>
                      Annuler
                    </Button>
                  </div>
                </>
              ) : (
                <>
                  <Form.Group className="mb-2">
                    <Form.Label className="small">Nom</Form.Label>
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
                  {parentTag && (
                    <div className="mb-2 small text-muted">
                      Parent : <Badge style={{ backgroundColor: parentTag.color || '#007bff' }}>&nbsp;</Badge>{' '}
                      {parentTag.name}
                      <Button
                        variant="link"
                        size="sm"
                        className="p-0 ms-2"
                        onClick={() => setParentId(null)}
                      >
                        <i className="fas fa-times" />
                      </Button>
                    </div>
                  )}
                  <Button size="sm" variant="primary" onClick={handleCreate} disabled={!newName.trim()}>
                    Creer
                  </Button>
                </>
              )}
            </Card.Body>
          </Card>
        </Col>

        {/* ---- Right column: tag tree ---- */}
        <Col md={8}>
          <Card>
            <Card.Header>Tags ({tags.length})</Card.Header>
            <Card.Body className="p-0">
              <TagTree
                tags={tags}
                onReorder={handleReorder}
                onEdit={handleEdit}
                onDelete={handleDeleteRequest}
                onAddChild={handleAddChild}
              />
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* ---- Delete confirmation ---- */}
      <ConfirmDialog
        show={!!deleteTarget}
        title="Supprimer le tag"
        message={`Supprimer le tag "${deleteTagObj?.name || ''}" ?`}
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />

      {/* ---- Tagged content overlay ---- */}
      {showTaggedContent && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0,0,0,0.5)',
            zIndex: 1050,
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'flex-start',
            paddingTop: 60,
            overflowY: 'auto'
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowTaggedContent(false)
          }}
        >
          <Card style={{ width: '80%', maxWidth: 900, maxHeight: '80vh' }}>
            <Card.Header className="d-flex justify-content-between align-items-center">
              <span>Contenu tagge</span>
              <Button variant="close" onClick={() => setShowTaggedContent(false)} />
            </Card.Header>
            <Card.Body style={{ overflowY: 'auto' }}>
              {loadingContent ? (
                <LoadingSpinner />
              ) : taggedContent.length === 0 ? (
                <p className="text-muted">Aucun contenu tagge</p>
              ) : (
                <ul className="taggedContent">
                  {taggedContent.map((item) => {
                    const tag = tags.find((t) => t.id === item.tag_id)
                    return (
                      <li key={item.id} className="d-flex align-items-start gap-2">
                        <Badge
                          style={{ backgroundColor: tag?.color || item.tag_color || '#007bff', marginTop: 4 }}
                        >
                          &nbsp;
                        </Badge>
                        <div>
                          <strong className="small">{tag?.name || item.tag_name || `Tag #${item.tag_id}`}</strong>
                          <div className="small text-muted">{item.text || item.content || ''}</div>
                        </div>
                      </li>
                    )
                  })}
                </ul>
              )}
            </Card.Body>
          </Card>
        </div>
      )}
    </div>
  )
}
