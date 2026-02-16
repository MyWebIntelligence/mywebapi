import { useState } from 'react'
import { Button, Form, Alert } from 'react-bootstrap'
import * as ops from '../../api/operationsApi'

export default function LLMSection({ landId }) {
  const [limit, setLimit] = useState(20)
  const [minRelevance, setMinRelevance] = useState(0)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleSubmit = async () => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await ops.llmValidate(landId, { limit, min_relevance: minRelevance })
      setResult(data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <p className="text-muted small">Valider les expressions via LLM (n&eacute;cessite OPENROUTER_API_KEY).</p>
      <Form.Group className="mb-2">
        <Form.Label className="small">Limite: {limit}</Form.Label>
        <Form.Range min={1} max={100} value={limit} onChange={(e) => setLimit(Number(e.target.value))} />
      </Form.Group>
      <Form.Group className="mb-2">
        <Form.Label className="small">Relevance minimum: {minRelevance}</Form.Label>
        <Form.Range min={0} max={100} value={minRelevance} onChange={(e) => setMinRelevance(Number(e.target.value))} />
      </Form.Group>
      <Button variant="primary" size="sm" onClick={handleSubmit} disabled={loading}>
        {loading ? 'Validation...' : 'Valider via LLM'}
      </Button>
      {result && <Alert variant="success" className="mt-2" dismissible onClose={() => setResult(null)}>Termin&eacute;. {JSON.stringify(result)}</Alert>}
      {error && <Alert variant="danger" className="mt-2">{error}</Alert>}
    </div>
  )
}
