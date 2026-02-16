import client from './client'

export async function getTags(landId) {
  const response = await client.get(`/v1/tags/${landId}/tags/`)
  return response.data
}

export async function createTag(landId, data) {
  const response = await client.post(`/v1/tags/${landId}/tags/`, data)
  return response.data
}

export async function updateTag(tagId, data) {
  const response = await client.put(`/v1/tags/${tagId}`, data)
  return response.data
}

export async function deleteTag(tagId) {
  const response = await client.delete(`/v1/tags/${tagId}`)
  return response.data
}

// Tagged content
export async function getTaggedContent(params = {}) {
  const response = await client.get('/v2/tagged-content', { params })
  return response.data
}

export async function createTaggedContent(data) {
  const response = await client.post('/v2/tagged-content', data)
  return response.data
}

export async function updateTaggedContent(id, data) {
  const response = await client.put(`/v2/tagged-content/${id}`, data)
  return response.data
}

export async function deleteTaggedContent(id) {
  const response = await client.delete(`/v2/tagged-content/${id}`)
  return response.data
}
