import { NavLink, useParams } from 'react-router-dom'
import { Nav } from 'react-bootstrap'
import { useAuth } from '../auth/AuthContext'

export default function Sidebar() {
  const { user } = useAuth()
  const { landId } = useParams()
  const isAdmin = user?.is_superuser || user?.is_admin

  return (
    <Nav className="flex-column p-3">
      <Nav.Item>
        <NavLink to="/" className="nav-link" end>
          Tableau de bord
        </NavLink>
      </Nav.Item>
      <Nav.Item>
        <NavLink to="/lands" className="nav-link">
          Projets (Lands)
        </NavLink>
      </Nav.Item>

      {landId && (
        <>
          <hr />
          <small className="text-muted px-3 mb-1">Land #{landId}</small>
          <Nav.Item>
            <NavLink to={`/lands/${landId}`} className="nav-link" end>
              Vue d'ensemble
            </NavLink>
          </Nav.Item>
          <Nav.Item>
            <NavLink to={`/lands/${landId}/expressions`} className="nav-link">
              Expressions
            </NavLink>
          </Nav.Item>
          <Nav.Item>
            <NavLink to={`/lands/${landId}/domains`} className="nav-link">
              Domaines
            </NavLink>
          </Nav.Item>
          <Nav.Item>
            <NavLink to={`/lands/${landId}/tags`} className="nav-link">
              Tags
            </NavLink>
          </Nav.Item>
          <Nav.Item>
            <NavLink to={`/lands/${landId}/export`} className="nav-link">
              Export
            </NavLink>
          </Nav.Item>
          <Nav.Item>
            <NavLink to={`/lands/${landId}/operations`} className="nav-link">
              Op&eacute;rations
            </NavLink>
          </Nav.Item>
        </>
      )}

      {isAdmin && (
        <>
          <hr />
          <small className="text-muted px-3 mb-1">Administration</small>
          <Nav.Item>
            <NavLink to="/admin/dashboard" className="nav-link">
              Dashboard Admin
            </NavLink>
          </Nav.Item>
          <Nav.Item>
            <NavLink to="/admin/users" className="nav-link">
              Utilisateurs
            </NavLink>
          </Nav.Item>
        </>
      )}
    </Nav>
  )
}
