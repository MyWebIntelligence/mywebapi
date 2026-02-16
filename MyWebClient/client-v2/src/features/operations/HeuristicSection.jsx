import { useState } from 'react'
import { Button, Form, Alert } from 'react-bootstrap'
import * as ops from '../../api/operationsApi'

export default function HeuristicSection({ landId }) {
  const [override, setOverride] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleSubmit = async () => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      let parsed = {}
      if (override.trim()) {
        parsed = JSON.parse(override)
      }
      const data = await ops.heuristicUpdate(landId, { heuristics_override: parsed })
      setResult(data)
    } catch (err) {
      if (err instanceof SyntaxError) {
        setError('JSON invalide')
      } else {
        setError(err.response?.data?.detail || 'Erreur')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <p className="text-muted small">Appliquer des r&egrave;gles heuristiques pour la mise &agrave; jour des expressions.</p>
      <Form.Group className="mb-2">
        <Form.Label className="small">R&egrave;gles heuristiques (JSON, optionnel)</Form.Label>
        <Form.Control
          as="textarea"
          rows={3}
          size="sm"
          value={override}
          onChange={(e) => setOverride(e.target.value)}
          placeholder='{"pattern": "value"}'
        />
      </Form.Group>
      <Button variant="primary" size="sm" onClick={handleSubmit} disabled={loading}>
        {loading ? 'Application...' : 'Appliquer les heuristiques'}
      </Button>
      {result && <Alert variant="success" className="mt-2" dismissible onClose={() => setResult(null)}>Termin&eacute;. {JSON.stringify(result)}</Alert>}
      {error && <Alert variant="danger" className="mt-2">{error}</Alert>}
    </div>
  )
}
