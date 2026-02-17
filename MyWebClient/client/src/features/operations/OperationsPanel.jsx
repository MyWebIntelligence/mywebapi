import { useParams } from 'react-router-dom'
import { Accordion } from 'react-bootstrap'
import CrawlSection from './CrawlSection'
import ConsolidateSection from './ConsolidateSection'
import ReadableSection from './ReadableSection'
import LLMSection from './LLMSection'
import SEORankSection from './SEORankSection'
import HeuristicSection from './HeuristicSection'
import MediaAnalysisSection from './MediaAnalysisSection'
import DictionarySection from './DictionarySection'
import URLSection from './URLSection'
import SerpAPISection from './SerpAPISection'
import DeleteExpressionsSection from './DeleteExpressionsSection'
import PipelineStats from './PipelineStats'

export default function OperationsPanel() {
  const { landId } = useParams()

  return (
    <div>
      <h4 className="mb-3">Op&eacute;rations - Land #{landId}</h4>
      <Accordion defaultActiveKey="0" alwaysOpen>
        <Accordion.Item eventKey="0">
          <Accordion.Header>Crawl</Accordion.Header>
          <Accordion.Body><CrawlSection landId={landId} /></Accordion.Body>
        </Accordion.Item>
        <Accordion.Item eventKey="1">
          <Accordion.Header>Consolidation</Accordion.Header>
          <Accordion.Body><ConsolidateSection landId={landId} /></Accordion.Body>
        </Accordion.Item>
        <Accordion.Item eventKey="2">
          <Accordion.Header>Contenu lisible (Readable)</Accordion.Header>
          <Accordion.Body><ReadableSection landId={landId} /></Accordion.Body>
        </Accordion.Item>
        <Accordion.Item eventKey="3">
          <Accordion.Header>Validation LLM</Accordion.Header>
          <Accordion.Body><LLMSection landId={landId} /></Accordion.Body>
        </Accordion.Item>
        <Accordion.Item eventKey="4">
          <Accordion.Header>SEO Rank</Accordion.Header>
          <Accordion.Body><SEORankSection landId={landId} /></Accordion.Body>
        </Accordion.Item>
        <Accordion.Item eventKey="5">
          <Accordion.Header>Heuristiques</Accordion.Header>
          <Accordion.Body><HeuristicSection landId={landId} /></Accordion.Body>
        </Accordion.Item>
        <Accordion.Item eventKey="6">
          <Accordion.Header>Analyse m&eacute;dia</Accordion.Header>
          <Accordion.Body><MediaAnalysisSection landId={landId} /></Accordion.Body>
        </Accordion.Item>
        <Accordion.Item eventKey="7">
          <Accordion.Header>Dictionnaire</Accordion.Header>
          <Accordion.Body><DictionarySection landId={landId} /></Accordion.Body>
        </Accordion.Item>
        <Accordion.Item eventKey="8">
          <Accordion.Header>Ajout d'URLs</Accordion.Header>
          <Accordion.Body><URLSection landId={landId} /></Accordion.Body>
        </Accordion.Item>
        <Accordion.Item eventKey="9">
          <Accordion.Header>SerpAPI</Accordion.Header>
          <Accordion.Body><SerpAPISection landId={landId} /></Accordion.Body>
        </Accordion.Item>
        <Accordion.Item eventKey="10">
          <Accordion.Header>Suppression d'expressions</Accordion.Header>
          <Accordion.Body><DeleteExpressionsSection landId={landId} /></Accordion.Body>
        </Accordion.Item>
        <Accordion.Item eventKey="11">
          <Accordion.Header>Statistiques du pipeline</Accordion.Header>
          <Accordion.Body><PipelineStats landId={landId} /></Accordion.Body>
        </Accordion.Item>
      </Accordion>
    </div>
  )
}
