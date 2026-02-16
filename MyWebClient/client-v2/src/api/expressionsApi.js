import client from './client'

export async function getExpressions(landId, params = {}) {
  const response = await client.get(`/v2/lands/${landId}/expressions`, { params })
  return response.data
}

export async function getExpression(landId, expressionId) {
  const response = await client.get(`/v2/lands/${landId}/expressions/${expressionId}`)
  return response.data
}

export async function updateExpression(landId, expressionId, data) {
  const response = await client.put(`/v2/lands/${landId}/expressions/${expressionId}`, data)
  return response.data
}

export async function deleteExpression(landId, expressionId) {
  const response = await client.delete(`/v2/lands/${landId}/expressions/${expressionId}`)
  return response.data
}
