import { Card, Badge, Button, ButtonGroup } from 'react-bootstrap'
import { useNavigate } from 'react-router-dom'

export default function LandCard({ land, onEdit, onDelete }) {
  const navigate = useNavigate()

  return (
    <Card className="h-100">
      <Card.Body>
        <Card.Title className="d-flex justify-content-between align-items-start">
          <span
            className="App-link"
            onClick={() => navigate(`/lands/${land.id}`)}
          >
            {land.name || land.title || `Land #${land.id}`}
          </span>
          <Badge bg={land.status === 'active' ? 'success' : 'secondary'} className="ms-2">
            {land.status || 'active'}
          </Badge>
        </Card.Title>
        <Card.Text className="text-muted small App-text-excerpt">
          {land.description || 'Pas de description'}
        </Card.Text>
        <div className="d-flex gap-2 flex-wrap mb-2">
          {land.expression_count != null && (
            <Badge bg="info">{land.expression_count} expr.</Badge>
          )}
          {land.domain_count != null && (
            <Badge bg="info">{land.domain_count} dom.</Badge>
          )}
        </div>
      </Card.Body>
      <Card.Footer className="bg-transparent">
        <ButtonGroup size="sm">
          <Button variant="outline-primary" onClick={() => navigate(`/lands/${land.id}`)}>
            Ouvrir
          </Button>
          <Button variant="outline-secondary" onClick={() => onEdit(land)}>
            Modifier
          </Button>
          <Button variant="outline-danger" onClick={() => onDelete(land)}>
            Supprimer
          </Button>
        </ButtonGroup>
      </Card.Footer>
    </Card>
  )
}
