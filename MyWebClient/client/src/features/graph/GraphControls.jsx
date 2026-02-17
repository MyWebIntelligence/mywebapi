import { Form, Button, ButtonGroup } from 'react-bootstrap'

export default function GraphControls({
  graphType,
  onGraphTypeChange,
  minRelevance,
  onMinRelevanceChange,
  maxDepth,
  onMaxDepthChange,
  showSimilarities,
  onShowSimilaritiesChange,
  onZoomIn,
  onZoomOut,
  onResetLayout,
}) {
  return (
    <div className="graph-controls">
      {/* Graph type selector */}
      <Form.Group className="mb-2">
        <Form.Label className="small fw-bold mb-1">Type</Form.Label>
        <Form.Select
          size="sm"
          value={graphType}
          onChange={(e) => onGraphTypeChange(e.target.value)}
        >
          <option value="page">Page</option>
          <option value="domain">Domain</option>
        </Form.Select>
      </Form.Group>

      {/* Min relevance slider */}
      <Form.Group className="mb-2">
        <Form.Label className="small fw-bold mb-1">
          Relevance min: {minRelevance}
        </Form.Label>
        <Form.Range
          min={0}
          max={10}
          step={1}
          value={minRelevance}
          onChange={(e) => onMinRelevanceChange(Number(e.target.value))}
        />
      </Form.Group>

      {/* Max depth slider */}
      <Form.Group className="mb-2">
        <Form.Label className="small fw-bold mb-1">
          Profondeur max: {maxDepth}
        </Form.Label>
        <Form.Range
          min={1}
          max={20}
          step={1}
          value={maxDepth}
          onChange={(e) => onMaxDepthChange(Number(e.target.value))}
        />
      </Form.Group>

      {/* Similarities checkbox */}
      <Form.Group className="mb-2">
        <Form.Check
          type="checkbox"
          id="show-similarities"
          label={<span className="small">Similarites</span>}
          checked={showSimilarities}
          onChange={(e) => onShowSimilaritiesChange(e.target.checked)}
        />
      </Form.Group>

      <hr className="my-2" />

      {/* Zoom and layout buttons */}
      <ButtonGroup size="sm" className="d-flex">
        <Button variant="outline-primary" onClick={onZoomIn} title="Zoom avant">
          <i className="fas fa-search-plus" />
        </Button>
        <Button variant="outline-primary" onClick={onZoomOut} title="Zoom arriere">
          <i className="fas fa-search-minus" />
        </Button>
        <Button variant="outline-primary" onClick={onResetLayout} title="Recalculer le layout">
          <i className="fas fa-redo" />
        </Button>
      </ButtonGroup>
    </div>
  )
}
