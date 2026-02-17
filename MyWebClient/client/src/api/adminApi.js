import client from './client'

export async function getUsers(params = {}) {
  const response = await client.get('/v2/admin/users', { params })
  return response.data
}

export async function getUser(userId) {
  const response = await client.get(`/v2/admin/users/${userId}`)
  return response.data
}

export async function updateUser(userId, data) {
  const response = await client.put(`/v2/admin/users/${userId}`, data)
  return response.data
}

export async function deleteUser(userId) {
  const response = await client.delete(`/v2/admin/users/${userId}`)
  return response.data
}

export async function blockUser(userId, data = {}) {
  const response = await client.post(`/v2/admin/users/${userId}/block`, data)
  return response.data
}

export async function unblockUser(userId) {
  const response = await client.post(`/v2/admin/users/${userId}/unblock`)
  return response.data
}

export async function setRole(userId, data) {
  const response = await client.post(`/v2/admin/users/${userId}/set-role`, data)
  return response.data
}

export async function forceResetPassword(userId) {
  const response = await client.post(`/v2/admin/users/${userId}/reset-password`)
  return response.data
}

export async function getAdminStats() {
  const response = await client.get('/v2/admin/stats')
  return response.data
}
