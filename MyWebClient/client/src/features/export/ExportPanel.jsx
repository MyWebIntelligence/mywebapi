import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { Card, Form, Button, Alert, Table, Badge, Row, Col } from 'react-bootstrap'
import * as exportApi from '../../api/exportApi'
import useJobPolling from '../../hooks/useJobPolling'

const EXPORT_TYPES = [
  { value: 'pagecsv', label: 'Page CSV', group: 'CSV' },
  { value: 'fullpagecsv', label: 'Full Page CSV', group: 'CSV' },
  { value: 'nodecsv', label: 'Node CSV', group: 'CSV' },
  { value: 'mediacsv', label: 'Media CSV', group: 'CSV' },
  { value: 'pagegexf', label: 'Page GEXF', group: 'R\u00e9seau' },
  { value: 'nodegexf', label: 'Node GEXF', group: 'R\u00e9seau' },
  { value: 'nodelinkcsv', label: 'Node Link CSV', group: 'R\u00e9seau' },
  { value: 'corpus', label: 'Corpus (ZIP)', group: 'Corpus' },
  { value: 'pseudolinks', label: 'Pseudo Links', group: 'Liens' },
  { value: 'pseudolinkspage', label: 'Pseudo Links Page', group: 'Liens' },
  { value: 'pseudolinksdomain', label: 'Pseudo Links Domain', group: 'Liens' },
  { value: 'tagmatrix', label: 'Tag Matrix', group: 'Tags' },
  { value: 'tagcontent', label: 'Tag Content', group: 'Tags' },
]

export default function ExportPanel() {
  const { landId } = useParams()
  const [exportType, setExportType] = useState('pagecsv')
  const [minRelevance, setMinRelevance] = useState(0)
  const [filename, setFilename] = useState('')
  const [loading, setLoading] = useState(false)
  const [jobId, setJobId] = useState(null)
  const [error, setError] = useState(null)
  const [recentJobs, setRecentJobs] = useState([])
  const { status, result, error: jobError, isPolling } = useJobPolling(jobId)

  const handleExport = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await exportApi.createExport({
        export_type: exportType,
        land_id: Number(landId),
        minimum_relevance: minRelevance,
        filename: filename || undefined,
      })
      setJobId(data.job_id || data.id)
      setRecentJobs((prev) => [{ id: data.job_id || data.id, type: exportType, status: 'pending' }, ...prev])
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur')
    } finally {
      setLoading(false)
    }
  }

  const handleDownload = async (jId) => {
    try {
      const response = await exportApi.downloadExport(jId)
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      const disposition = response.headers['content-disposition']
      const fname = disposition?.match(/filename="?(.+)"?/)?.[1] || `export_${jId}`
      link.setAttribute('download', fname)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch {
      setError('Erreur de t\u00e9l\u00e9chargement')
    }
  }

  return (
    <div>
      <h4 className="mb-3">Export - Land #{landId}</h4>

      <Row className="g-3">
        <Col md={6}>
          <Card>
            <Card.Header>Nouvel export</Card.Header>
            <Card.Body>
              <Form.Group className="mb-3">
                <Form.Label>Type d'export</Form.Label>
                <Form.Select value={exportType} onChange={(e) => setExportType(e.target.value)}>
                  {EXPORT_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      [{t.group}] {t.label}
                    </option>
                  ))}
                </Form.Select>
              </Form.Group>
              <Form.Group className="mb-3">
                <Form.Label>Relevance minimum: {minRelevance}</Form.Label>
                <Form.Range min={0} max={100} value={minRelevance} onChange={(e) => setMinRelevance(Number(e.target.value))} />
              </Form.Group>
              <Form.Group className="mb-3">
                <Form.Label>Nom de fichier (optionnel)</Form.Label>
                <Form.Control
                  size="sm"
                  value={filename}
                  onChange={(e) => setFilename(e.target.value)}
                  placeholder="mon_export"
                />
              </Form.Group>
              <Button
                variant="primary"
                onClick={handleExport}
                disabled={loading || isPolling}
              >
                {loading ? 'Lancement...' : isPolling ? 'Export en cours...' : 'Exporter'}
              </Button>
            </Card.Body>
          </Card>
        </Col>

        <Col md={6}>
          <Card>
            <Card.Header>Exports r&eacute;cents</Card.Header>
            <Card.Body>
              {recentJobs.length === 0 ? (
                <p className="text-muted small">Aucun export r&eacute;cent</p>
              ) : (
                <Table size="sm">
                  <thead>
                    <tr>
                      <th>Type</th>
                      <th>Statut</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentJobs.map((job) => (
                      <tr key={job.id}>
                        <td className="small">{job.type}</td>
                        <td>
                          <Badge bg={
                            job.id === jobId && result ? 'success' :
                            job.id === jobId && isPolling ? 'warning' : 'secondary'
                          }>
                            {job.id === jobId ? (result ? 'termin\u00e9' : status || 'en cours') : job.status}
                          </Badge>
                        </td>
                        <td>
                          {(job.id === jobId && result) && (
                            <Button size="sm" variant="outline-primary" onClick={() => handleDownload(job.id)}>
                              T&eacute;l&eacute;charger
                            </Button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              )}
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {(error || jobError) && (
        <Alert variant="danger" className="mt-3">{error || jobError}</Alert>
      )}
    </div>
  )
}
