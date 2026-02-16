import { Toast, ToastContainer as BSToastContainer } from 'react-bootstrap'

export default function ToastContainer({ toasts, onClose }) {
  return (
    <BSToastContainer position="top-end" className="p-3" style={{ zIndex: 9999 }}>
      {toasts.map((t) => (
        <Toast key={t.id} bg={t.variant} onClose={() => onClose(t.id)} autohide delay={5000}>
          <Toast.Header closeButton>
            <strong className="me-auto">
              {t.variant === 'success' ? 'Succes' : t.variant === 'danger' ? 'Erreur' : 'Info'}
            </strong>
          </Toast.Header>
          <Toast.Body className={t.variant === 'danger' || t.variant === 'success' ? 'text-white' : ''}>
            {t.message}
          </Toast.Body>
        </Toast>
      ))}
    </BSToastContainer>
  )
}
