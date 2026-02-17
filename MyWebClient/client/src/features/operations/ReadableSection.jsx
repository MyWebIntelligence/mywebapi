import { useState } from 'react'
import { Button, Form, Alert } from 'react-bootstrap'
import * as ops from '../../api/operationsApi'

export default function ReadableSection({ landId }) {
  const [limit, setLimit] = useState(50)
  const [depth, setDepth] = useState(5)
  const [mergeStrategy, setMergeStrategy] = useState('smart_merge')
  const [enableLlm, setEnableLlm] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleSubmit = async () => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await ops.readable(landId, {
        limit, depth, merge_strategy: mergeStrategy, enable_llm: enableLlm,
      })
      setResult(data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <p className="text-muted small">Extraire le contenu lisible des expressions.</p>
      <Form.Group className="mb-2">
        <Form.Label className="small">Strat&eacute;gie de merge</Form.Label>
        <Form.Select size="sm" value={mergeStrategy} onChange={(e) => setMergeStrategy(e.target.value)}>
          <option value="smart_merge">Smart merge</option>
          <option value="mercury_priority">Mercury priority</option>
          <option value="preserve_existing">Preserve existing</option>
        </Form.Select>
      </Form.Group>
      <Form.Group className="mb-2">
        <Form.Label className="small">Limite: {limit}</Form.Label>
        <Form.Range min={1} max={500} value={limit} onChange={(e) => setLimit(Number(e.target.value))} />
      </Form.Group>
      <Form.Group className="mb-2">
        <Form.Label className="small">Profondeur max: {depth}</Form.Label>
        <Form.Range min={0} max={10} value={depth} onChange={(e) => setDepth(Number(e.target.value))} />
      </Form.Group>
      <Form.Check
        className="mb-2"
        label="Activer LLM"
        checked={enableLlm}
        onChange={(e) => setEnableLlm(e.target.checked)}
      />
      <Button variant="primary" size="sm" onClick={handleSubmit} disabled={loading}>
        {loading ? 'Extraction...' : 'Extraire le contenu lisible'}
      </Button>
      {result && <Alert variant="success" className="mt-2" dismissible onClose={() => setResult(null)}>Termin&eacute;. {JSON.stringify(result)}</Alert>}
      {error && <Alert variant="danger" className="mt-2">{error}</Alert>}
    </div>
  )
}
