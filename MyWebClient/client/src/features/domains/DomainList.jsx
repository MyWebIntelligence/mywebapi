import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { Table, Button, Alert, Badge } from 'react-bootstrap'
import * as api from '../../api/domainsApi'
import Pagination from '../../components/Pagination'
import LoadingSpinner from '../../components/LoadingSpinner'
import EmptyState from '../../components/EmptyState'

export default function DomainList() {
  const { landId } = useParams()
  const [domains, setDomains] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(50)
  const [loading, setLoading] = useState(true)
  const [crawling, setCrawling] = useState(false)
  const [message, setMessage] = useState(null)

  const fetchDomains = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.getDomains({ land_id: landId, page, page_size: pageSize })
      setDomains(data.items || data)
      setTotal(data.total || (data.items || data).length)
    } catch (err) {
      console.error('Failed to fetch domains:', err)
    } finally {
      setLoading(false)
    }
  }, [landId, page, pageSize])

  useEffect(() => {
    fetchDomains()
  }, [fetchDomains])

  const handleCrawlAll = async () => {
    setCrawling(true)
    try {
      await api.crawlDomains(landId)
      setMessage({ type: 'success', text: 'Crawl des domaines lanc\u00e9' })
    } catch (err) {
      setMessage({ type: 'danger', text: err.response?.data?.detail || 'Erreur' })
    } finally {
      setCrawling(false)
    }
  }

  const handleRecrawl = async (domainId) => {
    try {
      await api.recrawlDomain(domainId)
      setMessage({ type: 'success', text: 'Recrawl lanc\u00e9' })
    } catch (err) {
      setMessage({ type: 'danger', text: 'Erreur recrawl' })
    }
  }

  const pageCount = Math.ceil(total / pageSize)

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h4 className="mb-0">Domaines - Land #{landId}</h4>
        <Button variant="primary" size="sm" onClick={handleCrawlAll} disabled={crawling}>
          {crawling ? 'Crawl en cours...' : 'Crawler les domaines'}
        </Button>
      </div>

      {message && (
        <Alert variant={message.type} dismissible onClose={() => setMessage(null)}>{message.text}</Alert>
      )}

      {loading ? (
        <LoadingSpinner />
      ) : domains.length === 0 ? (
        <EmptyState title="Aucun domaine" message="Les domaines apparaitront apr\u00e8s un crawl." />
      ) : (
        <>
          <Table hover responsive size="sm">
            <thead>
              <tr>
                <th>Nom</th>
                <th>Titre</th>
                <th>Expressions</th>
                <th>Statut</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {domains.map((d) => (
                <tr key={d.id}>
                  <td>
                    <a href={d.url || d.name} target="_blank" rel="noopener noreferrer" className="small">
                      {d.name || d.url}
                    </a>
                  </td>
                  <td className="small">{d.title || '—'}</td>
                  <td><Badge bg="info">{d.expression_count ?? '—'}</Badge></td>
                  <td>
                    <Badge bg={d.http_status === 200 ? 'success' : 'warning'}>
                      {d.http_status || '—'}
                    </Badge>
                  </td>
                  <td>
                    <Button variant="outline-primary" size="sm" onClick={() => handleRecrawl(d.id)}>
                      Recrawl
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
          <Pagination page={page} pageCount={pageCount} onPageChange={setPage} />
        </>
      )}
    </div>
  )
}
