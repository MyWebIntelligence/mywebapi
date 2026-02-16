import { useState } from 'react'
import { Button, Form, Alert, Row, Col } from 'react-bootstrap'
import * as ops from '../../api/operationsApi'

export default function SerpAPISection({ landId }) {
  const [query, setQuery] = useState('')
  const [engine, setEngine] = useState('google')
  const [lang, setLang] = useState('fr')
  const [datestart, setDatestart] = useState('')
  const [dateend, setDateend] = useState('')
  const [timestep, setTimestep] = useState('month')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleSubmit = async () => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await ops.serpapiUrls(landId, {
        query, engine, lang,
        datestart: datestart || undefined,
        dateend: dateend || undefined,
        timestep,
      })
      setResult(data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <p className="text-muted small">Rechercher des URLs via SerpAPI (n&eacute;cessite SERPAPI_API_KEY).</p>
      <Form.Group className="mb-2">
        <Form.Label className="small">Requ&ecirc;te</Form.Label>
        <Form.Control size="sm" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Votre recherche" />
      </Form.Group>
      <Row className="mb-2">
        <Col>
          <Form.Label className="small">Moteur</Form.Label>
          <Form.Select size="sm" value={engine} onChange={(e) => setEngine(e.target.value)}>
            <option value="google">Google</option>
            <option value="bing">Bing</option>
            <option value="duckduckgo">DuckDuckGo</option>
          </Form.Select>
        </Col>
        <Col>
          <Form.Label className="small">Langue</Form.Label>
          <Form.Select size="sm" value={lang} onChange={(e) => setLang(e.target.value)}>
            <option value="fr">Fran&ccedil;ais</option>
            <option value="en">English</option>
            <option value="de">Deutsch</option>
            <option value="es">Espa&ntilde;ol</option>
          </Form.Select>
        </Col>
        <Col>
          <Form.Label className="small">Pas de temps</Form.Label>
          <Form.Select size="sm" value={timestep} onChange={(e) => setTimestep(e.target.value)}>
            <option value="day">Jour</option>
            <option value="week">Semaine</option>
            <option value="month">Mois</option>
          </Form.Select>
        </Col>
      </Row>
      <Row className="mb-2">
        <Col>
          <Form.Label className="small">Date d&eacute;but</Form.Label>
          <Form.Control type="date" size="sm" value={datestart} onChange={(e) => setDatestart(e.target.value)} />
        </Col>
        <Col>
          <Form.Label className="small">Date fin</Form.Label>
          <Form.Control type="date" size="sm" value={dateend} onChange={(e) => setDateend(e.target.value)} />
        </Col>
      </Row>
      <Button variant="primary" size="sm" onClick={handleSubmit} disabled={loading || !query}>
        {loading ? 'Recherche...' : 'Rechercher des URLs'}
      </Button>
      {result && <Alert variant="success" className="mt-2" dismissible onClose={() => setResult(null)}>Termin&eacute;. {JSON.stringify(result)}</Alert>}
      {error && <Alert variant="danger" className="mt-2">{error}</Alert>}
    </div>
  )
}
