import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from './AuthContext'
import { Spinner } from 'react-bootstrap'

export default function AdminRoute() {
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

  if (!user.is_superuser && !user.is_admin) {
    return <Navigate to="/" replace />
  }

  return <Outlet />
}
