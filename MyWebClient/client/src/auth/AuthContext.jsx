import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import * as authApi from '../api/authApi'
import { setTokens, clearTokens, getAccessToken } from '../utils/tokenStorage'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  const checkAuth = useCallback(async () => {
    const token = getAccessToken()
    if (!token) {
      setUser(null)
      setLoading(false)
      return
    }
    try {
      const userData = await authApi.getMe()
      setUser(userData)
    } catch {
      clearTokens()
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    checkAuth()
  }, [checkAuth])

  // Listen for forced logout from the API interceptor
  useEffect(() => {
    const handleLogout = () => {
      setUser(null)
      navigate('/login')
    }
    window.addEventListener('auth:logout', handleLogout)
    return () => window.removeEventListener('auth:logout', handleLogout)
  }, [navigate])

  const login = useCallback(async (username, password) => {
    const data = await authApi.login(username, password)
    setTokens(data.access_token, data.refresh_token)
    const userData = await authApi.getMe()
    setUser(userData)
    return userData
  }, [])

  const register = useCallback(async (username, email, password) => {
    const data = await authApi.register(username, email, password)
    // Auto-login after registration if tokens returned
    if (data.access_token) {
      setTokens(data.access_token, data.refresh_token)
      const userData = await authApi.getMe()
      setUser(userData)
      return userData
    }
    return data
  }, [])

  const logout = useCallback(() => {
    clearTokens()
    setUser(null)
    navigate('/login')
  }, [navigate])

  const value = { user, loading, login, register, logout }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
