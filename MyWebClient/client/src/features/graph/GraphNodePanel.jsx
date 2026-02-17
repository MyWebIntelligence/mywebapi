import { Badge, Button } from 'react-bootstrap'

export default function GraphNodePanel({ node, onOpen, onClose }) {
  if (!node) return null

  return (
    <div className="graph-node-panel">
      <div className="d-flex justify-content-between align-items-start">
        <div className="flex-grow-1 me-3">
          <div className="d-flex align-items-center gap-2 mb-1">
            <strong>{node.label || `Node ${node.id}`}</strong>
            {node.relevance != null && (
              <Badge bg="info" title="Relevance">
                <i className="fas fa-star me-1" />
                {node.relevance}
              </Badge>
            )}
            {node.depth != null && (
              <Badge bg="secondary" title="Profondeur">
                <i className="fas fa-layer-group me-1" />
                {node.depth}
              </Badge>
            )}
          </div>

          {node.url && (
            <div className="mb-1">
              <a
                href={node.url}
                target="_blank"
                rel="noopener noreferrer"
                className="App-link small"
              >
                <i className="fas fa-external-link-alt me-1" />
                {node.url}
              </a>
            </div>
          )}

          <div className="small text-muted d-flex gap-3">
            {node.domain && (
              <span>
                <i className="fas fa-globe me-1" />
                {node.domain}
              </span>
            )}
            {node.sentiment != null && (
              <span>
                <i className="fas fa-smile me-1" />
                Sentiment: {Number(node.sentiment).toFixed(2)}
              </span>
            )}
          </div>
        </div>

        <div className="d-flex gap-1 flex-shrink-0">
          <Button size="sm" variant="primary" onClick={onOpen}>
            <i className="fas fa-folder-open me-1" />
            Ouvrir
          </Button>
          <Button size="sm" variant="outline-secondary" onClick={onClose}>
            <i className="fas fa-times" />
          </Button>
        </div>
      </div>
    </div>
  )
}
