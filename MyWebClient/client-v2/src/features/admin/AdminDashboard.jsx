import { useState, useEffect } from 'react'
import { Row, Col, Card, Alert } from 'react-bootstrap'
import { Link } from 'react-router-dom'
import * as adminApi from '../../api/adminApi'
import LoadingSpinner from '../../components/LoadingSpinner'

export default function AdminDashboard() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const fetch = async () => {
      try {
        const data = await adminApi.getAdminStats()
        setStats(data)
      } catch (err) {
        setError(err.response?.data?.detail || 'Erreur chargement stats')
      } finally {
        setLoading(false)
      }
    }
    fetch()
  }, [])

  if (loading) return <LoadingSpinner />
  if (error) return <Alert variant="danger">{error}</Alert>
  if (!stats) return null

  const cards = [
    { label: 'Utilisateurs totaux', value: stats.total_users, color: 'primary' },
    { label: 'Utilisateurs actifs', value: stats.active_users, color: 'success' },
    { label: 'Utilisateurs bloqu\u00e9s', value: stats.blocked_users, color: 'danger' },
    { label: 'Lands', value: stats.total_lands, color: 'info' },
    { label: 'Expressions', value: stats.total_expressions, color: 'info' },
    { label: 'Domaines', value: stats.total_domains, color: 'info' },
  ]

  return (
    <div>
      <h4 className="mb-3">Dashboard Administration</h4>

      <Row xs={2} md={3} className="g-3 mb-4">
        {cards.map((c, i) => (
          <Col key={i}>
            <Card className={`border-${c.color}`}>
              <Card.Body className="text-center">
                <div className={`fs-2 fw-bold text-${c.color}`}>{c.value}</div>
                <small className="text-muted">{c.label}</small>
              </Card.Body>
            </Card>
          </Col>
        ))}
      </Row>

      <Card>
        <Card.Header>Actions rapides</Card.Header>
        <Card.Body>
          <Link to="/admin/users" className="btn btn-outline-primary btn-sm me-2">
            G&eacute;rer les utilisateurs
          </Link>
        </Card.Body>
      </Card>
    </div>
  )
}
