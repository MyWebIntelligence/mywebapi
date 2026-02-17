import { useState, useEffect } from 'react'
import { Button, Alert, Card, Row, Col, Badge } from 'react-bootstrap'
import * as ops from '../../api/operationsApi'
import LoadingSpinner from '../../components/LoadingSpinner'

export default function PipelineStats({ landId }) {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [fixing, setFixing] = useState(false)
  const [error, setError] = useState(null)

  const fetchStats = async () => {
    setLoading(true)
    try {
      const data = await ops.getPipelineStats(landId)
      setStats(data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStats()
  }, [landId])

  const handleFix = async () => {
    setFixing(true)
    try {
      await ops.fixPipeline(landId)
      fetchStats()
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur')
    } finally {
      setFixing(false)
    }
  }

  if (loading) return <LoadingSpinner text="Chargement des statistiques..." />
  if (error) return <Alert variant="danger">{error}</Alert>
  if (!stats) return null

  return (
    <div>
      <Row className="g-2 mb-3">
        {Object.entries(stats).map(([key, value]) => (
          <Col xs={6} md={4} key={key}>
            <Card className="text-center">
              <Card.Body className="py-2">
                <div className="fw-bold">{typeof value === 'number' ? value : JSON.stringify(value)}</div>
                <small className="text-muted">{key.replace(/_/g, ' ')}</small>
              </Card.Body>
            </Card>
          </Col>
        ))}
      </Row>
      <Button variant="outline-warning" size="sm" onClick={handleFix} disabled={fixing}>
        {fixing ? 'R\u00e9paration...' : 'R\u00e9parer le pipeline'}
      </Button>
    </div>
  )
}
