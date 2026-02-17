import { Routes, Route } from 'react-router-dom'
import { AuthProvider } from '../../auth/AuthContext'
import ProtectedRoute from '../../auth/ProtectedRoute'
import AdminRoute from '../../auth/AdminRoute'
import AuthLayout from '../../layouts/AuthLayout'
import MainLayout from '../../layouts/MainLayout'
import ErrorBoundary from '../ErrorBoundary'
import LoginPage from '../../auth/LoginPage'
import RegisterPage from '../../auth/RegisterPage'
import ForgotPasswordPage from '../../auth/ForgotPasswordPage'
import ResetPasswordPage from '../../auth/ResetPasswordPage'
import Dashboard from '../../features/dashboard/Dashboard'
import LandList from '../../features/lands/LandList'
import LandDetail from '../../features/lands/LandDetail'
import ExpressionExplorer from '../../features/expressions/ExpressionExplorer'
import ExpressionDetail from '../../features/expressions/ExpressionDetail'
import DomainList from '../../features/domains/DomainList'
import TagManager from '../../features/tags/TagManager'
import ExportPanel from '../../features/export/ExportPanel'
import OperationsPanel from '../../features/operations/OperationsPanel'
import AdminDashboard from '../../features/admin/AdminDashboard'
import UserManagement from '../../features/admin/UserManagement'
import GraphViewer from '../../features/graph/GraphViewer'
import SearchResults from '../../features/search/SearchResults'
import LegacyExplorer from '../../features/legacy/LegacyExplorer'
import './App.css'

function NotFound() {
  return (
    <div className="text-center text-muted py-5">
      <h3>404</h3>
      <p>Page non trouv&eacute;e</p>
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <ErrorBoundary>
        <Routes>
          {/* Auth pages (minimal layout) */}
          <Route element={<AuthLayout />}>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
          </Route>

          {/* Protected app routes (main layout) */}
          <Route element={<ProtectedRoute />}>
            <Route element={<MainLayout />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/lands" element={<LandList />} />
              <Route path="/lands/:landId" element={<LandDetail />} />
              <Route path="/lands/:landId/explore" element={<LegacyExplorer />} />
              <Route path="/lands/:landId/expressions" element={<ExpressionExplorer />} />
              <Route path="/lands/:landId/expressions/:exprId" element={<ExpressionDetail />} />
              <Route path="/lands/:landId/domains" element={<DomainList />} />
              <Route path="/lands/:landId/tags" element={<TagManager />} />
              <Route path="/lands/:landId/export" element={<ExportPanel />} />
              <Route path="/lands/:landId/graph" element={<GraphViewer />} />
              <Route path="/lands/:landId/operations" element={<OperationsPanel />} />
              <Route path="/search" element={<SearchResults />} />
            </Route>
          </Route>

          {/* Admin routes */}
          <Route element={<AdminRoute />}>
            <Route element={<MainLayout />}>
              <Route path="/admin/dashboard" element={<AdminDashboard />} />
              <Route path="/admin/users" element={<UserManagement />} />
            </Route>
          </Route>

          {/* 404 */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </ErrorBoundary>
    </AuthProvider>
  )
}
