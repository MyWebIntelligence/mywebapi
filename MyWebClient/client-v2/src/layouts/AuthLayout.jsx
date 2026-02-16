import { Outlet } from 'react-router-dom'
import { Container, Card } from 'react-bootstrap'

export default function AuthLayout() {
  return (
    <Container
      className="d-flex align-items-center justify-content-center"
      style={{ minHeight: '100vh' }}
    >
      <Card style={{ width: '100%', maxWidth: 420, padding: '2rem' }}>
        <div className="text-center mb-3">
          <h4 className="text-primary fw-bold">MyWebIntelligence</h4>
        </div>
        <Outlet />
      </Card>
    </Container>
  )
}
