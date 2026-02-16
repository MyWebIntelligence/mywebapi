import client from './client'

export async function startCrawl(landId, options = {}) {
  const response = await client.post(`/v2/lands/${landId}/crawl`, options)
  return response.data
}

export async function consolidate(landId, options = {}) {
  const response = await client.post(`/v2/lands/${landId}/consolidate`, options)
  return response.data
}

export async function getLandStats(landId) {
  const response = await client.get(`/v2/lands/${landId}/stats`)
  return response.data
}

export async function getPipelineStats(landId) {
  const response = await client.get(`/v2/lands/${landId}/pipeline-stats`)
  return response.data
}

export async function fixPipeline(landId) {
  const response = await client.post(`/v2/lands/${landId}/fix-pipeline`)
  return response.data
}

export async function getJobStatus(jobId) {
  const response = await client.get(`/v1/jobs/${jobId}`)
  return response.data
}

// Content operations
export async function readable(landId, options = {}) {
  const response = await client.post(`/v2/lands/${landId}/readable`, options)
  return response.data
}

export async function llmValidate(landId, options = {}) {
  const response = await client.post(`/v2/lands/${landId}/llm-validate`, options)
  return response.data
}

export async function seoRank(landId, options = {}) {
  const response = await client.post(`/v2/lands/${landId}/seorank`, options)
  return response.data
}

export async function heuristicUpdate(landId, options = {}) {
  const response = await client.post(`/v2/lands/${landId}/heuristic-update`, options)
  return response.data
}

export async function mediaAnalysis(landId, options = {}) {
  const response = await client.post(`/v2/lands/${landId}/media-analysis-async`, options)
  return response.data
}

// URLs and dictionary
export async function addUrls(landId, urls) {
  const response = await client.post(`/v2/lands/${landId}/urls`, { urls })
  return response.data
}

export async function addTerms(landId, terms) {
  const response = await client.post(`/v2/lands/${landId}/terms`, { terms })
  return response.data
}

export async function populateDictionary(landId, options = {}) {
  const response = await client.post(`/v2/lands/${landId}/populate-dictionary`, options)
  return response.data
}

export async function getDictionaryStats(landId) {
  const response = await client.get(`/v2/lands/${landId}/dictionary-stats`)
  return response.data
}

export async function serpapiUrls(landId, options) {
  const response = await client.post(`/v2/lands/${landId}/serpapi-urls`, options)
  return response.data
}

export async function deleteExpressions(landId, maxrel) {
  const response = await client.delete(`/v2/lands/${landId}/expressions`, {
    data: { maxrel },
  })
  return response.data
}
