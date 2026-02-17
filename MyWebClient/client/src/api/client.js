import axios from 'axios'
import {
  getAccessToken,
  getRefreshToken,
  setTokens,
  clearTokens,
  isTokenExpired,
} from '../utils/tokenStorage'

const client = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

// Track in-flight refresh to avoid duplicate refresh calls
let refreshPromise = null

/**
 * Request interceptor: attach Authorization header
 */
client.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

/**
 * Response interceptor: handle 401 by refreshing the token
 */
client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    // Don't retry refresh or login requests
    if (
      originalRequest._retry ||
      originalRequest.url?.includes('/auth/login') ||
      originalRequest.url?.includes('/auth/refresh')
    ) {
      return Promise.reject(error)
    }

    if (error.response?.status === 401) {
      originalRequest._retry = true

      try {
        // Reuse an in-flight refresh if one exists
        if (!refreshPromise) {
          refreshPromise = refreshAccessToken()
        }
        await refreshPromise
        refreshPromise = null

        // Retry the original request with the new token
        const token = getAccessToken()
        originalRequest.headers.Authorization = `Bearer ${token}`
        return client(originalRequest)
      } catch (refreshError) {
        refreshPromise = null
        clearTokens()
        // Redirect to login - dispatch event for AuthContext to pick up
        window.dispatchEvent(new Event('auth:logout'))
        return Promise.reject(refreshError)
      }
    }

    return Promise.reject(error)
  }
)

async function refreshAccessToken() {
  const refreshToken = getRefreshToken()
  if (!refreshToken || isTokenExpired(refreshToken)) {
    throw new Error('No valid refresh token')
  }

  const response = await axios.post(
    '/api/v1/auth/refresh',
    null,
    { headers: { Authorization: `Bearer ${refreshToken}` } }
  )

  const { access_token, refresh_token } = response.data
  setTokens(access_token, refresh_token)
}

export default client
