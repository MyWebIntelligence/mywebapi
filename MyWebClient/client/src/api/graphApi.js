import client from './client'

export const getGraphData = (landId, params = {}) =>
  client.get(`/v2/lands/${landId}/graph`, { params }).then((r) => r.data)
