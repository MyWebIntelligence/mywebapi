import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Form, Button, Alert } from 'react-bootstrap'
import { useAuth } from './AuthContext'

const PASSWORD_REGEX = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$/

export default function RegisterPage() {
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const { register } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)

    if (password !== confirmPassword) {
      setError('Les mots de passe ne correspondent pas.')
      return
    }
    if (!PASSWORD_REGEX.test(password)) {
      setError(
        'Le mot de passe doit contenir au moins 8 caractères, une majuscule, une minuscule, un chiffre et un caractère spécial.'
      )
      return
    }

    setLoading(true)
    try {
      await register(username, email, password)
      navigate('/')
    } catch (err) {
      const msg = err.response?.data?.detail || 'Erreur lors de l\'inscription'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <h2 className="mb-4">Cr&eacute;er un compte</h2>
      <Form onSubmit={handleSubmit}>
        <Form.Group className="mb-3">
          <Form.Label>Identifiant</Form.Label>
          <Form.Control
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="Choisissez un identifiant"
            minLength={3}
            maxLength={50}
            required
            autoFocus
          />
        </Form.Group>
        <Form.Group className="mb-3">
          <Form.Label>Email</Form.Label>
          <Form.Control
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="votre@email.com"
            required
          />
        </Form.Group>
        <Form.Group className="mb-3">
          <Form.Label>Mot de passe</Form.Label>
          <Form.Control
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="8 caractères min, maj, min, chiffre, spécial"
            required
          />
        </Form.Group>
        <Form.Group className="mb-3">
          <Form.Label>Confirmer le mot de passe</Form.Label>
          <Form.Control
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            placeholder="Confirmez votre mot de passe"
            required
          />
        </Form.Group>
        {error && <Alert variant="danger">{error}</Alert>}
        <Button variant="primary" type="submit" disabled={loading} className="w-100">
          {loading ? 'Inscription...' : 'S\'inscrire'}
        </Button>
        <div className="mt-3 text-center">
          <span className="text-muted">D&eacute;j&agrave; un compte ?</span>{' '}
          <Link to="/login">Se connecter</Link>
        </div>
      </Form>
    </>
  )
}
