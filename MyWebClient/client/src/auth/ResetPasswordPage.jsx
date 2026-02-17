import { useState, useEffect } from 'react'
import { Link, useSearchParams, useNavigate } from 'react-router-dom'
import { Form, Button, Alert, InputGroup } from 'react-bootstrap'
import { resetPassword } from '../api/authApi'

const PASSWORD_REGEX = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$/

export default function ResetPasswordPage() {
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get('token')

  useEffect(() => {
    if (!token) {
      setError('Token de r\u00e9initialisation manquant ou invalide.')
    }
  }, [token])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (password !== confirmPassword) {
      setError('Les mots de passe ne correspondent pas.')
      return
    }
    if (!PASSWORD_REGEX.test(password)) {
      setError(
        'Le mot de passe doit contenir au moins 8 caract\u00e8res, une majuscule, une minuscule, un chiffre et un caract\u00e8re sp\u00e9cial.'
      )
      return
    }

    setLoading(true)
    setError('')
    setMessage('')
    try {
      await resetPassword(token, password)
      setMessage(
        'Votre mot de passe a \u00e9t\u00e9 r\u00e9initialis\u00e9 avec succ\u00e8s. Redirection vers la connexion...'
      )
      setTimeout(() => navigate('/login'), 3000)
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur lors de la r\u00e9initialisation.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <h2 className="mb-4">R&eacute;initialiser le mot de passe</h2>
      {token ? (
        <Form onSubmit={handleSubmit}>
          <Form.Group className="mb-3">
            <Form.Label>Nouveau mot de passe</Form.Label>
            <InputGroup>
              <Form.Control
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
              <Button
                variant="outline-secondary"
                onMouseDown={() => setShowPassword(true)}
                onMouseUp={() => setShowPassword(false)}
                onMouseLeave={() => setShowPassword(false)}
              >
                {showPassword ? 'Cacher' : 'Voir'}
              </Button>
            </InputGroup>
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>Confirmer le nouveau mot de passe</Form.Label>
            <Form.Control
              type={showPassword ? 'text' : 'password'}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
            />
          </Form.Group>
          {message && <Alert variant="success">{message}</Alert>}
          {error && <Alert variant="danger">{error}</Alert>}
          <Button variant="primary" type="submit" disabled={loading} className="w-100">
            {loading ? 'R\u00e9initialisation...' : 'R\u00e9initialiser le mot de passe'}
          </Button>
        </Form>
      ) : (
        <Alert variant="danger">{error || 'Token invalide ou expir\u00e9.'}</Alert>
      )}
      <div className="mt-3 text-center">
        <Link to="/login">Retour &agrave; la connexion</Link>
      </div>
    </>
  )
}
