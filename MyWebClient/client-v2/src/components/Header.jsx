import { Navbar, Container, Badge, Button } from 'react-bootstrap'
import { useAuth } from '../auth/AuthContext'

export default function Header() {
  const { user, logout } = useAuth()

  return (
    <Navbar bg="dark" variant="dark" className="px-3" style={{ height: 56 }}>
      <Container fluid>
        <Navbar.Brand href="/" className="fw-bold">
          MyWebIntelligence
        </Navbar.Brand>
        {user && (
          <div className="d-flex align-items-center gap-2">
            <span className="text-light small">{user.username}</span>
            {(user.is_superuser || user.is_admin) && (
              <Badge bg="warning" text="dark">
                admin
              </Badge>
            )}
            <Button variant="outline-light" size="sm" onClick={logout}>
              D&eacute;connexion
            </Button>
          </div>
        )}
      </Container>
    </Navbar>
  )
}
