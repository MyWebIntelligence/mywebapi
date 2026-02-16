import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { Card, Row, Col, Badge, Button, ListGroup } from 'react-bootstrap'
import * as landsApi from '../../api/landsApi'
import LoadingSpinner from '../../components/LoadingSpinner'

export default function LandDetail() {
  const { landId } = useParams()
  const navigate = useNavigate()
  const [land, setLand] = useState(null)
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetch = async () => {
      setLoading(true)
      try {
        const [landData, statsData] = await Promise.all([
          landsApi.getLand(landId),
          landsApi.getLandStats(landId).catch(() => null),
        ])
        setLand(landData)
        setStats(statsData)
      } catch (err) {
        console.error('Failed to fetch land:', err)
      } finally {
        setLoading(false)
      }
    }
    fetch()
  }, [landId])

  if (loading) return <LoadingSpinner />
  if (!land) return <div className="text-danger p-3">Land not found</div>

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h4 className="mb-0">{land.name || land.title || `Land #${land.id}`}</h4>
        <Badge bg={land.status === 'active' ? 'success' : 'secondary'}>
          {land.status || 'active'}
        </Badge>
      </div>

      {land.description && <p className="text-muted">{land.description}</p>}

      <Row className="g-3 mb-4">
        <Col md={4}>
          <Card>
            <Card.Body className="text-center">
              <div className="fs-3 fw-bold text-primary">
                {stats?.total_expressions ?? '—'}
              </div>
              <small className="text-muted">Expressions</small>
            </Card.Body>
          </Card>
        </Col>
        <Col md={4}>
          <Card>
            <Card.Body className="text-center">
              <div className="fs-3 fw-bold text-info">
                {stats?.total_domains ?? '—'}
              </div>
              <small className="text-muted">Domaines</small>
            </Card.Body>
          </Card>
        </Col>
        <Col md={4}>
          <Card>
            <Card.Body className="text-center">
              <div className="fs-3 fw-bold text-success">
                {stats?.total_media ?? '—'}
              </div>
              <small className="text-muted">M&eacute;dias</small>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      <Card className="mb-3">
        <Card.Header>Navigation rapide</Card.Header>
        <ListGroup variant="flush">
          <ListGroup.Item action as={Link} to={`/lands/${landId}/expressions`}>
            Expressions
          </ListGroup.Item>
          <ListGroup.Item action as={Link} to={`/lands/${landId}/domains`}>
            Domaines
          </ListGroup.Item>
          <ListGroup.Item action as={Link} to={`/lands/${landId}/tags`}>
            Tags
          </ListGroup.Item>
          <ListGroup.Item action as={Link} to={`/lands/${landId}/export`}>
            Export
          </ListGroup.Item>
          <ListGroup.Item action as={Link} to={`/lands/${landId}/operations`}>
            Op&eacute;rations
          </ListGroup.Item>
        </ListGroup>
      </Card>

      {land.start_urls && land.start_urls.length > 0 && (
        <Card>
          <Card.Header>URLs de d&eacute;part</Card.Header>
          <ListGroup variant="flush">
            {land.start_urls.map((url, i) => (
              <ListGroup.Item key={i} className="small">
                <a href={url} target="_blank" rel="noopener noreferrer">
                  {url}
                </a>
              </ListGroup.Item>
            ))}
          </ListGroup>
        </Card>
      )}

      <div className="mt-3">
        <Button
          variant="primary"
          size="sm"
          onClick={() => navigate(`/lands/${landId}/operations`)}
        >
          Lancer un crawl
        </Button>
      </div>
    </div>
  )
}
