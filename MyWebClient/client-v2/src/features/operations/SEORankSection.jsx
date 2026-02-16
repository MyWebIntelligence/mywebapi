import { useState } from 'react'
import { Button, Form, Alert } from 'react-bootstrap'
import * as ops from '../../api/operationsApi'

export default function SEORankSection({ landId }) {
  const [limit, setLimit] = useState(50)
  const [depth, setDepth] = useState(5)
  const [minRelevance, setMinRelevance] = useState(0)
  const [forceRefresh, setForceRefresh] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleSubmit = async () => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await ops.seoRank(landId, { limit, depth, min_relevance: minRelevance, force_refresh: forceRefresh })
      setResult(data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <p className="text-muted small">Enrichir les expressions avec les donn&eacute;es SEO.</p>
      <Form.Group className="mb-2">
        <Form.Label className="small">Limite: {limit}</Form.Label>
        <Form.Range min={1} max={500} value={limit} onChange={(e) => setLimit(Number(e.target.value))} />
      </Form.Group>
      <Form.Group className="mb-2">
        <Form.Label className="small">Profondeur max: {depth}</Form.Label>
        <Form.Range min={0} max={10} value={depth} onChange={(e) => setDepth(Number(e.target.value))} />
      </Form.Group>
      <Form.Group className="mb-2">
        <Form.Label className="small">Relevance minimum: {minRelevance}</Form.Label>
        <Form.Range min={0} max={100} value={minRelevance} onChange={(e) => setMinRelevance(Number(e.target.value))} />
      </Form.Group>
      <Form.Check className="mb-2" label="Forcer le rafraichissement" checked={forceRefresh} onChange={(e) => setForceRefresh(e.target.checked)} />
      <Button variant="primary" size="sm" onClick={handleSubmit} disabled={loading}>
        {loading ? 'Enrichissement...' : 'Enrichir SEO'}
      </Button>
      {result && <Alert variant="success" className="mt-2" dismissible onClose={() => setResult(null)}>Termin&eacute;. {JSON.stringify(result)}</Alert>}
      {error && <Alert variant="danger" className="mt-2">{error}</Alert>}
    </div>
  )
}
