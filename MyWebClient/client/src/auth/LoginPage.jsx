import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Form, Button, Alert } from 'react-bootstrap'
import { useAuth } from './AuthContext'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      await login(username, password)
      navigate('/')
    } catch (err) {
      const msg = err.response?.data?.detail || 'Erreur d\'authentification'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <h2 className="mb-4">Connexion</h2>
      <Form onSubmit={handleSubmit}>
        <Form.Group className="mb-3">
          <Form.Label>Identifiant</Form.Label>
          <Form.Control
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="Votre identifiant"
            required
            autoFocus
          />
        </Form.Group>
        <Form.Group className="mb-3">
          <Form.Label>Mot de passe</Form.Label>
          <Form.Control
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Votre mot de passe"
            required
          />
        </Form.Group>
        {error && <Alert variant="danger">{error}</Alert>}
        <Button variant="primary" type="submit" disabled={loading} className="w-100">
          {loading ? 'Connexion...' : 'Se connecter'}
        </Button>
        <div className="mt-3 text-center">
          <Link to="/forgot-password">Mot de passe oubli&eacute; ?</Link>
        </div>
        <div className="mt-2 text-center">
          <span className="text-muted">Pas de compte ?</span>{' '}
          <Link to="/register">Cr&eacute;er un compte</Link>
        </div>
      </Form>
    </>
  )
}
