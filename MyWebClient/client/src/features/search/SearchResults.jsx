import { useState, useEffect, useCallback } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { Table, Form, Button, Alert, InputGroup, Badge } from 'react-bootstrap'
import * as landsApi from '../../api/landsApi'
import * as expressionsApi from '../../api/expressionsApi'
import LoadingSpinner from '../../components/LoadingSpinner'
import EmptyState from '../../components/EmptyState'
import Pagination from '../../components/Pagination'

/**
 * Page de recherche globale.
 * Recherche des expressions a travers tous les lands de l'utilisateur.
 */
export default function SearchResults() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const initialQuery = searchParams.get('q') || ''

  const [query, setQuery] = useState(initialQuery)
  const [results, setResults] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [searched, setSearched] = useState(false)

  const pageCount = Math.ceil(total / pageSize)

  const performSearch = useCallback(async (searchQuery, searchPage = 1) => {
    if (!searchQuery || searchQuery.trim() === '') return

    setLoading(true)
    setError(null)
    setSearched(true)

    try {
      // Fetch all user lands first
      const landsData = await landsApi.getLands({ page: 1, pageSize: 200 })
      const lands = landsData.items || landsData || []

      if (lands.length === 0) {
        setResults([])
        setTotal(0)
        setLoading(false)
        return
      }

      // Search across all lands in parallel
      const allResults = []
      const promises = lands.map(async (land) => {
        try {
          const data = await expressionsApi.getExpressions(land.id, {
            search: searchQuery.trim(),
            page: 1,
            page_size: 200,
          })
          const items = data.items || data || []
          // Attach land info to each result
          return items.map((expr) => ({
            ...expr,
            land_id: land.id,
            land_name: land.name || land.title || `Land #${land.id}`,
          }))
        } catch {
          // Skip lands that fail (e.g., permission issues)
          return []
        }
      })

      const landResults = await Promise.all(promises)
      landResults.forEach((items) => allResults.push(...items))

      // Sort by relevance (descending)
      allResults.sort((a, b) => (b.relevance || 0) - (a.relevance || 0))

      setTotal(allResults.length)

      // Client-side pagination
      const start = (searchPage - 1) * pageSize
      setResults(allResults.slice(start, start + pageSize))
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur lors de la recherche')
      setResults([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [pageSize])

  // Run search on initial load if query param exists
  useEffect(() => {
    if (initialQuery) {
      performSearch(initialQuery, 1)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!query.trim()) return
    setPage(1)
    setSearchParams({ q: query.trim() })
    performSearch(query.trim(), 1)
  }

  const handlePageChange = (newPage) => {
    setPage(newPage)
    performSearch(query.trim(), newPage)
  }

  return (
    <div>
      <h4 className="mb-3">
        <i className="fas fa-search me-2" />
        Recherche
      </h4>

      {/* Search form */}
      <Form onSubmit={handleSubmit} className="mb-4">
        <InputGroup>
          <Form.Control
            type="text"
            placeholder="Entrez un terme de recherche..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ borderColor: '#ccc' }}
          />
          <Button type="submit" variant="primary" disabled={loading || !query.trim()}>
            <i className="fas fa-search me-1" />
            Rechercher
          </Button>
        </InputGroup>
      </Form>

      {error && <Alert variant="danger">{error}</Alert>}

      {/* No query yet */}
      {!searched && !loading && (
        <EmptyState
          title="Entrez un terme de recherche"
          message="Recherchez des expressions a travers tous vos projets."
        />
      )}

      {/* Loading */}
      {loading && <LoadingSpinner text="Recherche en cours..." />}

      {/* Results */}
      {searched && !loading && (
        <>
          {results.length === 0 ? (
            <EmptyState
              title="Aucun resultat"
              message={`Aucune expression trouvee pour "${searchParams.get('q') || query}".`}
            />
          ) : (
            <>
              <div className="mb-2 text-muted small">
                {total} resultat{total > 1 ? 's' : ''} trouves pour &laquo;&nbsp;{searchParams.get('q') || query}&nbsp;&raquo;
              </div>

              <Table hover responsive size="sm">
                <thead>
                  <tr>
                    <th>Projet</th>
                    <th>Titre</th>
                    <th>Domaine</th>
                    <th style={{ width: 80 }}>Relevance</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((expr) => (
                    <tr
                      key={`${expr.land_id}-${expr.id}`}
                      style={{ cursor: 'pointer' }}
                      onClick={() => navigate(`/lands/${expr.land_id}/expressions/${expr.id}`)}
                    >
                      <td>
                        <Badge bg="light" text="dark" style={{ border: '1px solid #ccc' }}>
                          {expr.land_name}
                        </Badge>
                      </td>
                      <td className="App-text-excerpt" style={{ maxWidth: 350 }}>
                        {expr.title || expr.url || '(sans titre)'}
                      </td>
                      <td className="small text-muted">
                        {expr.domain_name || '---'}
                      </td>
                      <td>
                        <Badge bg={expr.relevance > 50 ? 'success' : expr.relevance > 20 ? 'warning' : 'secondary'}>
                          {expr.relevance ?? '---'}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>

              {pageCount > 1 && (
                <Pagination
                  page={page}
                  pageCount={pageCount}
                  onPageChange={handlePageChange}
                />
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}
