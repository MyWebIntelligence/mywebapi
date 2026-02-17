import { useState } from 'react'
import { Button, Form, Alert } from 'react-bootstrap'
import * as ops from '../../api/operationsApi'

export default function MediaAnalysisSection({ landId }) {
  const [depth, setDepth] = useState(5)
  const [minrel, setMinrel] = useState(0)
  const [batchSize, setBatchSize] = useState(50)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleSubmit = async () => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await ops.mediaAnalysis(landId, { depth, minrel, batch_size: batchSize })
      setResult(data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <p className="text-muted small">Analyser les m&eacute;dias (images) des expressions.</p>
      <Form.Group className="mb-2">
        <Form.Label className="small">Profondeur: {depth}</Form.Label>
        <Form.Range min={0} max={10} value={depth} onChange={(e) => setDepth(Number(e.target.value))} />
      </Form.Group>
      <Form.Group className="mb-2">
        <Form.Label className="small">Relevance min: {minrel}</Form.Label>
        <Form.Range min={0} max={100} value={minrel} onChange={(e) => setMinrel(Number(e.target.value))} />
      </Form.Group>
      <Form.Group className="mb-2">
        <Form.Label className="small">Taille du batch: {batchSize}</Form.Label>
        <Form.Range min={10} max={200} value={batchSize} onChange={(e) => setBatchSize(Number(e.target.value))} />
      </Form.Group>
      <Button variant="primary" size="sm" onClick={handleSubmit} disabled={loading}>
        {loading ? 'Analyse...' : 'Analyser les m\u00e9dias'}
      </Button>
      {result && <Alert variant="success" className="mt-2" dismissible onClose={() => setResult(null)}>Termin&eacute;. {JSON.stringify(result)}</Alert>}
      {error && <Alert variant="danger" className="mt-2">{error}</Alert>}
    </div>
  )
}
