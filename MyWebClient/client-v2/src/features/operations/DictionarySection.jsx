import { useState, useEffect } from 'react'
import { Button, Form, Alert, Badge } from 'react-bootstrap'
import * as ops from '../../api/operationsApi'

export default function DictionarySection({ landId }) {
  const [terms, setTerms] = useState('')
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    ops.getDictionaryStats(landId).then(setStats).catch(() => {})
  }, [landId])

  const handleAddTerms = async () => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const termsList = terms.split('\n').map((t) => t.trim()).filter(Boolean)
      if (termsList.length === 0) return
      const data = await ops.addTerms(landId, termsList)
      setResult(data)
      setTerms('')
      ops.getDictionaryStats(landId).then(setStats).catch(() => {})
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur')
    } finally {
      setLoading(false)
    }
  }

  const handlePopulate = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await ops.populateDictionary(landId, { force_refresh: true })
      setResult(data)
      ops.getDictionaryStats(landId).then(setStats).catch(() => {})
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <p className="text-muted small">G&eacute;rer le dictionnaire de mots-cl&eacute;s du land.</p>
      {stats && (
        <div className="mb-2">
          <Badge bg="info">Entr&eacute;es: {stats.total_entries ?? '—'}</Badge>
        </div>
      )}
      <Form.Group className="mb-2">
        <Form.Label className="small">Mots-cl&eacute;s (un par ligne)</Form.Label>
        <Form.Control
          as="textarea"
          rows={4}
          size="sm"
          value={terms}
          onChange={(e) => setTerms(e.target.value)}
          placeholder="mot-cle 1&#10;mot-cle 2"
        />
      </Form.Group>
      <div className="d-flex gap-2">
        <Button variant="primary" size="sm" onClick={handleAddTerms} disabled={loading}>
          Ajouter
        </Button>
        <Button variant="outline-primary" size="sm" onClick={handlePopulate} disabled={loading}>
          Peupler automatiquement
        </Button>
      </div>
      {result && <Alert variant="success" className="mt-2" dismissible onClose={() => setResult(null)}>Termin&eacute;. {JSON.stringify(result)}</Alert>}
      {error && <Alert variant="danger" className="mt-2">{error}</Alert>}
    </div>
  )
}
