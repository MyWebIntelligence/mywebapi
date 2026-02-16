import { useState } from 'react'
import { Button, Form, Alert } from 'react-bootstrap'
import * as ops from '../../api/operationsApi'
import ConfirmDialog from '../../components/ConfirmDialog'

export default function DeleteExpressionsSection({ landId }) {
  const [maxrel, setMaxrel] = useState(0)
  const [showConfirm, setShowConfirm] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleDelete = async () => {
    setShowConfirm(false)
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await ops.deleteExpressions(landId, maxrel)
      setResult(data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <p className="text-muted small">Supprimer les expressions sous un seuil de relevance.</p>
      <Form.Group className="mb-2">
        <Form.Label className="small">Seuil de relevance: {maxrel}</Form.Label>
        <Form.Range min={0} max={100} step={1} value={maxrel} onChange={(e) => setMaxrel(Number(e.target.value))} />
      </Form.Group>
      <Button variant="danger" size="sm" onClick={() => setShowConfirm(true)} disabled={loading}>
        {loading ? 'Suppression...' : `Supprimer (relevance < ${maxrel})`}
      </Button>
      <ConfirmDialog
        show={showConfirm}
        title="Suppression d'expressions"
        message={`Voulez-vous supprimer toutes les expressions avec une relevance inf\u00e9rieure \u00e0 ${maxrel} ? Cette action est irr\u00e9versible.`}
        confirmText="Supprimer"
        onConfirm={handleDelete}
        onCancel={() => setShowConfirm(false)}
      />
      {result && <Alert variant="success" className="mt-2" dismissible onClose={() => setResult(null)}>Suppression termin&eacute;e. {JSON.stringify(result)}</Alert>}
      {error && <Alert variant="danger" className="mt-2">{error}</Alert>}
    </div>
  )
}
