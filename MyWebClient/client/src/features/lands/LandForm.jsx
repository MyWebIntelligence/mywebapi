import { useState, useEffect, useRef } from 'react'
import { Modal, Form, Button } from 'react-bootstrap'

export default function LandForm({ show, land, onSave, onClose }) {
  const isEdit = !!land?.id
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [startUrls, setStartUrls] = useState('')
  const [crawlDepth, setCrawlDepth] = useState(2)
  const [loading, setLoading] = useState(false)
  const fileInputRef = useRef(null)

  const handleFileUpload = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (evt) => {
      const lines = evt.target.result
        .split(/\r?\n/)
        .map((l) => l.trim())
        .filter(Boolean)
      setStartUrls((prev) => {
        const existing = prev.trim()
        return existing ? existing + '\n' + lines.join('\n') : lines.join('\n')
      })
    }
    reader.readAsText(file)
    e.target.value = ''
  }

  useEffect(() => {
    if (land) {
      setName(land.name || land.title || '')
      setDescription(land.description || '')
      setStartUrls(
        Array.isArray(land.start_urls) ? land.start_urls.join('\n') : (land.start_urls || '')
      )
      setCrawlDepth(land.crawl_depth || 2)
    } else {
      setName('')
      setDescription('')
      setStartUrls('')
      setCrawlDepth(2)
    }
  }, [land])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    const urls = startUrls
      .split('\n')
      .map((u) => u.trim())
      .filter(Boolean)
    await onSave({
      name,
      description,
      start_urls: urls,
      crawl_depth: crawlDepth,
    })
    setLoading(false)
  }

  return (
    <Modal show={show} onHide={onClose} centered>
      <Form onSubmit={handleSubmit}>
        <Modal.Header closeButton>
          <Modal.Title>{isEdit ? 'Modifier le projet' : 'Nouveau projet'}</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Form.Group className="mb-3">
            <Form.Label>Nom</Form.Label>
            <Form.Control
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Nom du projet"
              required
              autoFocus
            />
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>Description</Form.Label>
            <Form.Control
              as="textarea"
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Description du projet"
            />
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>URLs de d&eacute;part (une par ligne)</Form.Label>
            <Form.Control
              as="textarea"
              rows={4}
              value={startUrls}
              onChange={(e) => setStartUrls(e.target.value)}
              placeholder="https://example.com"
            />
            <div className="mt-2 d-flex align-items-center gap-2">
              <Button
                variant="outline-secondary"
                size="sm"
                onClick={() => fileInputRef.current?.click()}
              >
                Importer un fichier .txt
              </Button>
              <Form.Text className="text-muted">
                Fichier texte avec une URL par ligne
              </Form.Text>
              <input
                ref={fileInputRef}
                type="file"
                accept=".txt,text/plain"
                className="d-none"
                onChange={handleFileUpload}
              />
            </div>
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>Profondeur de crawl: {crawlDepth}</Form.Label>
            <Form.Range
              min={1}
              max={5}
              value={crawlDepth}
              onChange={(e) => setCrawlDepth(Number(e.target.value))}
            />
          </Form.Group>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={onClose}>
            Annuler
          </Button>
          <Button variant="primary" type="submit" disabled={loading}>
            {loading ? 'Enregistrement...' : isEdit ? 'Enregistrer' : 'Cr\u00e9er'}
          </Button>
        </Modal.Footer>
      </Form>
    </Modal>
  )
}
