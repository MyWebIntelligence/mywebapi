import client from './client'

export async function createExport(data) {
  const response = await client.post('/v2/export/', data)
  return response.data
}

export async function getExportJob(jobId) {
  const response = await client.get(`/v2/export/jobs/${jobId}`)
  return response.data
}

export async function downloadExport(jobId) {
  const response = await client.get(`/v2/export/download/${jobId}`, {
    responseType: 'blob',
  })
  return response
}

export async function cancelExport(jobId) {
  const response = await client.delete(`/v2/export/jobs/${jobId}`)
  return response.data
}

// Shortcut endpoints
export async function exportCsv(data) {
  const response = await client.post('/v2/export/csv', data)
  return response.data
}

export async function exportGexf(data) {
  const response = await client.post('/v2/export/gexf', data)
  return response.data
}

export async function exportCorpus(data) {
  const response = await client.post('/v2/export/corpus', data)
  return response.data
}

export async function exportNodelinkcsv(data) {
  const response = await client.post('/v2/export/nodelinkcsv', data)
  return response.data
}
