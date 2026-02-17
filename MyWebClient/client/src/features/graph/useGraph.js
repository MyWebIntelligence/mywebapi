import { useState, useEffect, useCallback } from 'react'
import Graph from 'graphology'
import forceAtlas2 from 'graphology-layout-forceatlas2'
import { getGraphData } from '../../api/graphApi'

/**
 * Custom hook for fetching graph data and building a graphology instance.
 * @param {number|string} landId - The land ID to fetch graph data for
 * @param {object} options - Graph options
 * @param {string} options.type - Graph type: 'page' or 'domain' (default 'page')
 * @param {number} options.minRelevance - Minimum relevance filter (default 0)
 * @param {number} options.maxDepth - Maximum depth filter (default 10)
 * @param {boolean} options.includeSimilarities - Include similarity edges (default true)
 * @returns {{ graph: Graph|null, loading: boolean, error: string|null, reload: function }}
 */
export default function useGraph(landId, options = {}) {
  const {
    type = 'page',
    minRelevance = 0,
    maxDepth = 10,
    includeSimilarities = true,
  } = options

  const [graph, setGraph] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const fetchGraph = useCallback(async () => {
    if (!landId) return

    setLoading(true)
    setError(null)
    setGraph(null)

    try {
      const data = await getGraphData(landId, {
        type,
        min_relevance: minRelevance,
        max_depth: maxDepth,
        include_similarities: includeSimilarities,
      })

      const g = new Graph({ multi: true, type: 'directed' })

      // Add nodes
      if (data.nodes && Array.isArray(data.nodes)) {
        data.nodes.forEach((node) => {
          if (!g.hasNode(node.id)) {
            g.addNode(node.id, {
              label: node.label || node.title || `Node ${node.id}`,
              url: node.url || '',
              relevance: node.relevance ?? 0,
              depth: node.depth ?? 0,
              domain: node.domain || '',
              sentiment: node.sentiment ?? null,
              type: node.type || type,
              size: Math.max(3, (node.relevance ?? 0) * 10 + 3),
              color: '#007bff',
            })
          }
        })
      }

      // Add edges
      if (data.edges && Array.isArray(data.edges)) {
        data.edges.forEach((edge, i) => {
          if (g.hasNode(edge.source) && g.hasNode(edge.target)) {
            g.addEdge(edge.source, edge.target, {
              weight: edge.weight ?? 1,
              type: edge.type || 'link',
              color: edge.type === 'similarity' ? '#ccc' : '#999',
            })
          }
        })
      }

      // Run community detection to assign colors
      try {
        const louvain = await import('graphology-communities-louvain')
        const communities = louvain.default(g)
        const palette = [
          '#007bff', '#28a745', '#dc3545', '#ffc107', '#17a2b8',
          '#6610f2', '#e83e8c', '#fd7e14', '#20c997', '#6f42c1',
          '#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4', '#ffeaa7',
        ]
        g.forEachNode((nodeId) => {
          const community = communities[nodeId] ?? 0
          g.setNodeAttribute(nodeId, 'community', community)
          g.setNodeAttribute(nodeId, 'color', palette[community % palette.length])
        })
      } catch {
        // Community detection is optional; proceed without it
      }

      // Adjust node sizes based on degree
      g.forEachNode((nodeId) => {
        const degree = g.degree(nodeId)
        const relevance = g.getNodeAttribute(nodeId, 'relevance') || 0
        g.setNodeAttribute(nodeId, 'size', Math.max(3, degree * 1.5 + relevance * 5 + 3))
      })

      // Run ForceAtlas2 synchronous layout
      forceAtlas2.assign(g, { iterations: 100 })

      setGraph(g)
    } catch (err) {
      console.error('Failed to fetch graph data:', err)
      setError(err.response?.data?.detail || err.message || 'Failed to load graph data')
    } finally {
      setLoading(false)
    }
  }, [landId, type, minRelevance, maxDepth, includeSimilarities])

  useEffect(() => {
    fetchGraph()
  }, [fetchGraph])

  return { graph, loading, error, reload: fetchGraph }
}
