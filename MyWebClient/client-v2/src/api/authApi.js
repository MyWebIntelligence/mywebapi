import axios from 'axios'
import client from './client'

/**
 * Login with username and password.
 * Uses form-encoded body as required by OAuth2PasswordRequestForm.
 */
export async function login(username, password) {
  const params = new URLSearchParams()
  params.append('username', username)
  params.append('password', password)

  const response = await axios.post('/api/v1/auth/login', params, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
  return response.data // { access_token, refresh_token, token_type }
}

/**
 * Register a new user account.
 * Uses V2 auth endpoint (to be created in Session 5-6).
 */
export async function register(username, email, password) {
  const response = await axios.post('/api/v2/auth/register', {
    username,
    email,
    password,
  })
  return response.data
}

/**
 * Get the currently authenticated user's profile.
 */
export async function getMe() {
  const response = await client.get('/v1/auth/me')
  return response.data
}

/**
 * Request a password reset email.
 */
export async function forgotPassword(email) {
  const response = await axios.post('/api/v2/auth/forgot-password', { email })
  return response.data
}

/**
 * Reset password using a token.
 */
export async function resetPassword(token, newPassword) {
  const response = await axios.post('/api/v2/auth/reset-password', {
    token,
    new_password: newPassword,
  })
  return response.data
}
