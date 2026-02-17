import { useState } from 'react'
import { Button, Alert } from 'react-bootstrap'
import * as ops from '../../api/operationsApi'

export default function ConsolidateSection({ landId }) {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleConsolidate = async () => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await ops.consolidate(landId)
      setResult(data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur lors de la consolidation')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <p className="text-muted small">Consolider les donn&eacute;es (liens, m&eacute;dias, stats).</p>
      <Button variant="primary" size="sm" onClick={handleConsolidate} disabled={loading}>
        {loading ? 'Consolidation...' : 'Consolider'}
      </Button>
      {result && (
        <Alert variant="success" className="mt-2" dismissible onClose={() => setResult(null)}>
          Consolidation termin&eacute;e. {JSON.stringify(result)}
        </Alert>
      )}
      {error && <Alert variant="danger" className="mt-2">{error}</Alert>}
    </div>
  )
}
