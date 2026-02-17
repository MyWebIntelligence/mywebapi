import { Navbar, Container, Badge, Button, Form } from 'react-bootstrap'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export default function Header() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [search, setSearch] = useState('')

  const handleSearch = (e) => {
    e.preventDefault()
    if (search.trim()) {
      navigate(`/search?q=${encodeURIComponent(search.trim())}`)
    }
  }

  return (
    <Navbar bg="light" variant="light" className="App-header px-3 border-bottom" style={{ height: 60 }}>
      <Container fluid>
        <Navbar.Brand href="/" className="fw-bold">
          <i className="fas fa-globe me-2" />
          MyWebIntelligence
        </Navbar.Brand>

        {user && (
          <Form className="d-flex mx-auto" style={{ maxWidth: 400 }} onSubmit={handleSearch}>
            <Form.Control
              size="sm"
              type="search"
              placeholder="Rechercher des expressions..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </Form>
        )}

        {user && (
          <div className="d-flex align-items-center gap-2">
            <i className="fas fa-user me-1" />
            <span className="small">{user.username}</span>
            {(user.is_superuser || user.is_admin) && (
              <Badge bg="primary">admin</Badge>
            )}
            <Button variant="outline-danger" size="sm" onClick={logout}>
              <i className="fas fa-sign-out-alt me-1" />
              D&eacute;connexion
            </Button>
          </div>
        )}
      </Container>
    </Navbar>
  )
}
