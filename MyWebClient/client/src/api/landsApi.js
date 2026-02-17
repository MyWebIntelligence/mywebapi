import client from './client'

export async function getLands({ page = 1, pageSize = 20, nameFilter = '', statusFilter = '' } = {}) {
  const params = { page, page_size: pageSize }
  if (nameFilter) params.name_filter = nameFilter
  if (statusFilter) params.status_filter = statusFilter
  const response = await client.get('/v2/lands/', { params })
  return response.data
}

export async function getLand(landId) {
  const response = await client.get(`/v2/lands/${landId}`)
  return response.data
}

export async function createLand(data) {
  const response = await client.post('/v2/lands/', data)
  return response.data
}

export async function updateLand(landId, data) {
  const response = await client.put(`/v2/lands/${landId}`, data)
  return response.data
}

export async function deleteLand(landId) {
  const response = await client.delete(`/v2/lands/${landId}`)
  return response.data
}

export async function getLandStats(landId) {
  const response = await client.get(`/v2/lands/${landId}/stats`)
  return response.data
}
