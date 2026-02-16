const ACCESS_TOKEN_KEY = 'mwi_access_token'
const REFRESH_TOKEN_KEY = 'mwi_refresh_token'

export function setTokens(accessToken, refreshToken) {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken)
  if (refreshToken) {
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
  }
}

export function getAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY)
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
}

/**
 * Decode JWT payload without verification (client-side only).
 * Returns null if token is invalid.
 */
export function decodeToken(token) {
  if (!token) return null
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return null
    const payload = JSON.parse(atob(parts[1]))
    return payload
  } catch {
    return null
  }
}

/**
 * Check if a JWT token is expired (with 30s buffer).
 */
export function isTokenExpired(token) {
  const payload = decodeToken(token)
  if (!payload || !payload.exp) return true
  const now = Math.floor(Date.now() / 1000)
  return payload.exp < now + 30 // 30s buffer
}
