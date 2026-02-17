import { useState } from 'react'
import { Button, Form, ProgressBar, Alert } from 'react-bootstrap'
import * as ops from '../../api/operationsApi'
import useJobPolling from '../../hooks/useJobPolling'

export default function CrawlSection({ landId }) {
  const [jobId, setJobId] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const { status, progress, result, error: jobError, isPolling } = useJobPolling(jobId)

  const handleCrawl = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await ops.startCrawl(landId)
      setJobId(data.job_id || data.id)
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur lors du lancement du crawl')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <p className="text-muted small">Lancer le crawl des URLs du land.</p>
      <Button
        variant="primary"
        size="sm"
        onClick={handleCrawl}
        disabled={loading || isPolling}
      >
        {loading ? 'Lancement...' : isPolling ? 'Crawl en cours...' : 'Lancer le crawl'}
      </Button>

      {isPolling && (
        <div className="mt-2">
          <ProgressBar
            now={progress ?? 0}
            label={`${progress ?? 0}%`}
            animated
            striped
          />
          <small className="text-muted">Statut: {status}</small>
        </div>
      )}

      {result && (
        <Alert variant="success" className="mt-2" dismissible onClose={() => setJobId(null)}>
          Crawl termin&eacute; avec succ&egrave;s.
        </Alert>
      )}

      {(error || jobError) && (
        <Alert variant="danger" className="mt-2">{error || jobError}</Alert>
      )}
    </div>
  )
}
