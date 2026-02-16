import client from './client'

export async function getDomains(params = {}) {
  const response = await client.get('/v2/domains/', { params })
  return response.data
}

export async function getDomainStats(landId) {
  const response = await client.get('/v2/domains/stats', { params: { land_id: landId } })
  return response.data
}

export async function crawlDomains(landId, options = {}) {
  const response = await client.post('/v2/domains/crawl', { land_id: landId, ...options })
  return response.data
}

export async function recrawlDomain(domainId) {
  const response = await client.post(`/v2/domains/${domainId}/recrawl`)
  return response.data
}
