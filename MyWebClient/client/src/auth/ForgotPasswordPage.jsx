import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Form, Button, Alert } from 'react-bootstrap'
import { forgotPassword } from '../api/authApi'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setMessage('')
    setError('')
    try {
      await forgotPassword(email)
      setMessage(
        'Si un compte est associ\u00e9 \u00e0 cet email, un lien de r\u00e9initialisation a \u00e9t\u00e9 envoy\u00e9.'
      )
      setEmail('')
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur lors de la demande.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <h2 className="mb-4">Mot de passe oubli&eacute;</h2>
      <Form onSubmit={handleSubmit}>
        <Form.Group className="mb-3">
          <Form.Label>Adresse e-mail</Form.Label>
          <Form.Control
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="votre@email.com"
            required
            autoFocus
          />
        </Form.Group>
        {message && <Alert variant="success">{message}</Alert>}
        {error && <Alert variant="danger">{error}</Alert>}
        <Button variant="primary" type="submit" disabled={loading} className="w-100">
          {loading ? 'Envoi en cours...' : 'Envoyer le lien de r\u00e9initialisation'}
        </Button>
      </Form>
      <div className="mt-3 text-center">
        <Link to="/login">Retour &agrave; la connexion</Link>
      </div>
    </>
  )
}
