import { useState, useRef, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Alert } from 'react-bootstrap'
import Sigma from 'sigma'
import forceAtlas2 from 'graphology-layout-forceatlas2'
import LoadingSpinner from '../../components/LoadingSpinner'
import GraphControls from './GraphControls'
import GraphNodePanel from './GraphNodePanel'
import useGraph from './useGraph'

export default function GraphViewer() {
  const { landId } = useParams()
  const navigate = useNavigate()
  const containerRef = useRef(null)
  const sigmaRef = useRef(null)

  const [selectedNode, setSelectedNode] = useState(null)
  const [graphType, setGraphType] = useState('page')
  const [minRelevance, setMinRelevance] = useState(0)
  const [maxDepth, setMaxDepth] = useState(10)
  const [showSimilarities, setShowSimilarities] = useState(true)

  const { graph, loading, error, reload } = useGraph(landId, {
    type: graphType,
    minRelevance,
    maxDepth,
    includeSimilarities: showSimilarities,
  })

  // Create / destroy Sigma instance when graph is ready
  useEffect(() => {
    if (!graph || !containerRef.current) return

    // Clean up previous instance
    if (sigmaRef.current) {
      sigmaRef.current.kill()
      sigmaRef.current = null
    }

    const sigma = new Sigma(graph, containerRef.current, {
      renderLabels: true,
      labelRenderedSizeThreshold: 6,
      labelFont: 'sans-serif',
      labelSize: 12,
      labelColor: { color: '#333' },
      defaultEdgeColor: '#ccc',
      defaultEdgeType: 'arrow',
      minCameraRatio: 0.1,
      maxCameraRatio: 10,
    })

    // Node click: select node
    sigma.on('clickNode', ({ node }) => {
      const attrs = graph.getNodeAttributes(node)
      setSelectedNode({ id: node, ...attrs })
    })

    // Node double click: navigate to expression detail
    sigma.on('doubleClickNode', ({ node }) => {
      navigate(`/lands/${landId}/expressions/${node}`)
    })

    // Click on stage: deselect
    sigma.on('clickStage', () => {
      setSelectedNode(null)
    })

    sigmaRef.current = sigma

    return () => {
      if (sigmaRef.current) {
        sigmaRef.current.kill()
        sigmaRef.current = null
      }
    }
  }, [graph, landId, navigate])

  const handleZoomIn = useCallback(() => {
    if (!sigmaRef.current) return
    const camera = sigmaRef.current.getCamera()
    camera.animatedZoom({ duration: 300 })
  }, [])

  const handleZoomOut = useCallback(() => {
    if (!sigmaRef.current) return
    const camera = sigmaRef.current.getCamera()
    camera.animatedUnzoom({ duration: 300 })
  }, [])

  const handleResetLayout = useCallback(() => {
    if (!graph) return
    forceAtlas2.assign(graph, { iterations: 100 })
    if (sigmaRef.current) {
      sigmaRef.current.refresh()
    }
  }, [graph])

  const handleOpenExpression = useCallback(() => {
    if (selectedNode) {
      navigate(`/lands/${landId}/expressions/${selectedNode.id}`)
    }
  }, [selectedNode, landId, navigate])

  const handleClosePanel = useCallback(() => {
    setSelectedNode(null)
  }, [])

  if (loading) return <LoadingSpinner text="Chargement du graphe..." />

  if (error) {
    return (
      <Alert variant="danger">
        <i className="fas fa-exclamation-triangle me-2" />
        {error}
      </Alert>
    )
  }

  return (
    <div className="graph-container">
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />

      <GraphControls
        graphType={graphType}
        onGraphTypeChange={setGraphType}
        minRelevance={minRelevance}
        onMinRelevanceChange={setMinRelevance}
        maxDepth={maxDepth}
        onMaxDepthChange={setMaxDepth}
        showSimilarities={showSimilarities}
        onShowSimilaritiesChange={setShowSimilarities}
        onZoomIn={handleZoomIn}
        onZoomOut={handleZoomOut}
        onResetLayout={handleResetLayout}
      />

      {selectedNode && (
        <GraphNodePanel
          node={selectedNode}
          onOpen={handleOpenExpression}
          onClose={handleClosePanel}
        />
      )}
    </div>
  )
}
