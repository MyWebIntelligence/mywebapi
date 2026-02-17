import client from './client'

export async function getExpressions(landId, params = {}) {
  const response = await client.get(`/v2/lands/${landId}/expressions`, { params })
  return response.data
}

export async function getExpression(exprId) {
  const response = await client.get(`/v2/expressions/${exprId}`)
  return response.data
}

export async function updateExpression(exprId, data) {
  const response = await client.put(`/v2/expressions/${exprId}`, data)
  return response.data
}

export async function deleteExpression(exprId) {
  const response = await client.delete(`/v2/expressions/${exprId}`)
  return response.data
}

export async function getNeighbors(exprId, params = {}) {
  const response = await client.get(`/v2/expressions/${exprId}/neighbors`, { params })
  return response.data
}
