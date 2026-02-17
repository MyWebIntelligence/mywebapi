import { useState, useEffect } from 'react'
import { Row, Col, Card, Alert, Button } from 'react-bootstrap'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import * as landsApi from '../../api/landsApi'
import * as adminApi from '../../api/adminApi'
import LoadingSpinner from '../../components/LoadingSpinner'

/**
 * Dashboard principal de l'application.
 * Affiche les statistiques et les projets recents de l'utilisateur.
 * Pour les admins, affiche aussi les stats globales.
 */
export default function Dashboard() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [lands, setLands] = useState([])
  const [adminStats, setAdminStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const isAdmin = user?.is_superuser || user?.role === 'admin'

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      setError(null)
      try {
        // Fetch user's lands
        const landsData = await landsApi.getLands({ page: 1, pageSize: 100 })
        const landsList = landsData.items || landsData || []
        setLands(landsList)

        // If admin, also fetch global stats
        if (isAdmin) {
          try {
            const stats = await adminApi.getAdminStats()
            setAdminStats(stats)
          } catch {
            // Admin stats are optional, don't block the dashboard
          }
        }
      } catch (err) {
        setError(err.response?.data?.detail || 'Erreur lors du chargement des donnees')
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [isAdmin])

  if (loading) return <LoadingSpinner />

  if (error) {
    return <Alert variant="danger">{error}</Alert>
  }

  // Compute user-level stats from fetched lands
  const totalLands = lands.length
  const totalExpressions = lands.reduce((sum, l) => sum + (l.expression_count || l.expressions_count || 0), 0)
  const totalDomains = lands.reduce((sum, l) => sum + (l.domain_count || l.domains_count || 0), 0)
  const activeJobs = lands.reduce((sum, l) => sum + (l.active_jobs || 0), 0)

  // Use admin stats if available (more accurate)
  const statsCards = [
    {
      label: 'Total Lands',
      value: adminStats ? adminStats.total_lands : totalLands,
      icon: 'fas fa-map',
      color: 'primary',
    },
    {
      label: 'Total Expressions',
      value: adminStats ? adminStats.total_expressions : totalExpressions,
      icon: 'fas fa-file-alt',
      color: 'success',
    },
    {
      label: 'Total Domaines',
      value: adminStats ? adminStats.total_domains : totalDomains,
      icon: 'fas fa-globe',
      color: 'info',
    },
    {
      label: 'Jobs actifs',
      value: adminStats ? (adminStats.active_jobs || 0) : activeJobs,
      icon: 'fas fa-tasks',
      color: 'warning',
    },
  ]

  // Recent lands (last 5)
  const recentLands = [...lands]
    .sort((a, b) => {
      const dateA = a.updated_at || a.created_at || ''
      const dateB = b.updated_at || b.created_at || ''
      return dateB.localeCompare(dateA)
    })
    .slice(0, 5)

  return (
    <div>
      <h4 className="mb-3">
        <i className="fas fa-tachometer-alt me-2" />
        Tableau de bord
      </h4>

      {/* Stats cards */}
      <Row xs={2} md={4} className="g-3 mb-4">
        {statsCards.map((card, i) => (
          <Col key={i}>
            <Card className={`border-${card.color} h-100`}>
              <Card.Body className="text-center">
                <i className={`${card.icon} fs-3 text-${card.color} mb-2 d-block`} />
                <div className={`fs-2 fw-bold text-${card.color}`}>
                  {card.value ?? '---'}
                </div>
                <small className="text-muted">{card.label}</small>
              </Card.Body>
            </Card>
          </Col>
        ))}
      </Row>

      <Row>
        {/* Recent projects */}
        <Col md={8}>
          <Card className="mb-4">
            <Card.Header>
              <i className="fas fa-clock me-2" />
              Mes projets recents
            </Card.Header>
            <Card.Body>
              {recentLands.length === 0 ? (
                <p className="text-muted mb-0">
                  Aucun projet. Creez votre premier projet pour commencer.
                </p>
              ) : (
                <div className="list-group list-group-flush">
                  {recentLands.map((land) => (
                    <Link
                      key={land.id}
                      to={`/lands/${land.id}`}
                      className="list-group-item list-group-item-action d-flex justify-content-between align-items-center"
                      style={{ borderColor: '#ccc' }}
                    >
                      <div>
                        <div className="fw-bold">{land.name || land.title || `Land #${land.id}`}</div>
                        {(land.description || land.seed_urls) && (
                          <small className="text-muted">
                            {land.description
                              ? land.description.substring(0, 80) + (land.description.length > 80 ? '...' : '')
                              : Array.isArray(land.seed_urls)
                                ? `${land.seed_urls.length} URL(s)`
                                : ''}
                          </small>
                        )}
                      </div>
                      <div className="text-end">
                        <small className="text-muted d-block">
                          {land.expression_count || land.expressions_count || 0} expr.
                        </small>
                        <small className="text-muted">
                          {land.domain_count || land.domains_count || 0} dom.
                        </small>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </Card.Body>
          </Card>
        </Col>

        {/* Quick actions */}
        <Col md={4}>
          <Card className="mb-4">
            <Card.Header>
              <i className="fas fa-bolt me-2" />
              Actions rapides
            </Card.Header>
            <Card.Body className="d-grid gap-2">
              <Button
                variant="primary"
                onClick={() => navigate('/lands')}
              >
                <i className="fas fa-plus me-2" />
                Nouveau projet
              </Button>
              {lands.length > 0 && (
                <Button
                  variant="outline-primary"
                  onClick={() => navigate(`/lands/${lands[0].id}/export`)}
                >
                  <i className="fas fa-download me-2" />
                  Voir les exports
                </Button>
              )}
              {isAdmin && (
                <Button
                  variant="outline-secondary"
                  onClick={() => navigate('/admin/dashboard')}
                >
                  <i className="fas fa-shield-alt me-2" />
                  Administration
                </Button>
              )}
            </Card.Body>
          </Card>

          {/* User info */}
          {user && (
            <Card>
              <Card.Header>
                <i className="fas fa-user me-2" />
                Mon compte
              </Card.Header>
              <Card.Body className="small">
                <div><strong>Utilisateur:</strong> {user.username || user.email}</div>
                <div><strong>Email:</strong> {user.email}</div>
                {isAdmin && (
                  <div><strong>Role:</strong> <span className="text-primary">Administrateur</span></div>
                )}
                <div><strong>Projets:</strong> {totalLands}</div>
              </Card.Body>
            </Card>
          )}
        </Col>
      </Row>
    </div>
  )
}
