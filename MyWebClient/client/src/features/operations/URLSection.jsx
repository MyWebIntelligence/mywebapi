import { useState } from 'react'
import { Button, Form, Alert } from 'react-bootstrap'
import * as ops from '../../api/operationsApi'

export default function URLSection({ landId }) {
  const [urls, setUrls] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleSubmit = async () => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const urlList = urls.split('\n').map((u) => u.trim()).filter(Boolean)
      if (urlList.length === 0) return
      const data = await ops.addUrls(landId, urlList)
      setResult(data)
      setUrls('')
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <p className="text-muted small">Ajouter des URLs au land (une par ligne).</p>
      <Form.Group className="mb-2">
        <Form.Control
          as="textarea"
          rows={5}
          size="sm"
          value={urls}
          onChange={(e) => setUrls(e.target.value)}
          placeholder="https://example.com/page1&#10;https://example.com/page2"
        />
      </Form.Group>
      <Button variant="primary" size="sm" onClick={handleSubmit} disabled={loading}>
        {loading ? 'Ajout...' : 'Ajouter les URLs'}
      </Button>
      {result && <Alert variant="success" className="mt-2" dismissible onClose={() => setResult(null)}>URLs ajout&eacute;es. {JSON.stringify(result)}</Alert>}
      {error && <Alert variant="danger" className="mt-2">{error}</Alert>}
    </div>
  )
}
