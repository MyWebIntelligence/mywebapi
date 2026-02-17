import { NavLink, useParams } from 'react-router-dom'
import { Nav } from 'react-bootstrap'
import { useAuth } from '../auth/AuthContext'

export default function Sidebar() {
  const { user } = useAuth()
  const { landId } = useParams()
  const isAdmin = user?.is_superuser || user?.is_admin

  const link = (to, icon, label, end) => (
    <Nav.Item>
      <NavLink to={to} className="nav-link py-2" end={end}>
        <i className={`fas fa-${icon} me-2`} style={{ width: 16, textAlign: 'center' }} />
        {label}
      </NavLink>
    </Nav.Item>
  )

  return (
    <Nav className="flex-column">
      <h6 className="text-muted text-uppercase small px-3 mt-2 mb-1">Navigation</h6>
      {link('/', 'tachometer-alt', 'Tableau de bord', true)}
      {link('/lands', 'project-diagram', 'Projets (Lands)')}

      {landId && (
        <>
          <hr className="my-2" />
          <h6 className="text-muted text-uppercase small px-3 mb-1">
            <i className="fas fa-map me-1" />
            Land #{landId}
          </h6>
          {link(`/lands/${landId}`, 'info-circle', 'Vue d\u2019ensemble', true)}
          {link(`/lands/${landId}/expressions`, 'file-alt', 'Expressions')}
          {link(`/lands/${landId}/domains`, 'globe', 'Domaines')}
          {link(`/lands/${landId}/tags`, 'tags', 'Tags')}
          {link(`/lands/${landId}/graph`, 'share-alt', 'Graphe r\u00e9seau')}
          {link(`/lands/${landId}/export`, 'download', 'Export')}
          {link(`/lands/${landId}/operations`, 'cogs', 'Op\u00e9rations')}
        </>
      )}

      {isAdmin && (
        <>
          <hr className="my-2" />
          <h6 className="text-muted text-uppercase small px-3 mb-1">
            <i className="fas fa-shield-alt me-1" />
            Administration
          </h6>
          {link('/admin/dashboard', 'chart-bar', 'Dashboard Admin')}
          {link('/admin/users', 'users', 'Utilisateurs')}
        </>
      )}
    </Nav>
  )
}
