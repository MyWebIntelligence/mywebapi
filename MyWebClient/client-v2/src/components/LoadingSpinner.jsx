import { Spinner } from 'react-bootstrap'

export default function LoadingSpinner({ text = 'Chargement...' }) {
  return (
    <div className="d-flex align-items-center justify-content-center p-5">
      <Spinner animation="border" variant="primary" size="sm" className="me-2" />
      <span className="text-muted">{text}</span>
    </div>
  )
}
