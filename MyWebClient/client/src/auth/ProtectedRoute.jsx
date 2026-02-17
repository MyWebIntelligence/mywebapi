import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from './AuthContext'
import { Spinner } from 'react-bootstrap'

export default function ProtectedRoute() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="d-flex align-items-center justify-content-center" style={{ height: '100vh' }}>
        <Spinner animation="border" variant="primary" />
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
