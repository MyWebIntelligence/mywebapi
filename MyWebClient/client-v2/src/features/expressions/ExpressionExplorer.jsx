import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Table, Form, Button, Badge } from 'react-bootstrap'
import * as api from '../../api/expressionsApi'
import FilterSlider from '../../components/FilterSlider'
import Pagination from '../../components/Pagination'
import LoadingSpinner from '../../components/LoadingSpinner'
import EmptyState from '../../components/EmptyState'
import ConfirmDialog from '../../components/ConfirmDialog'
import useKeyboardShortcuts from '../../hooks/useKeyboardShortcuts'

export default function ExpressionExplorer() {
  const { landId } = useParams()
  const navigate = useNavigate()
  const [expressions, setExpressions] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)
  const [minRelevance, setMinRelevance] = useState(0)
  const [maxDepth, setMaxDepth] = useState(5)
  const [sortColumn, setSortColumn] = useState('relevance')
  const [sortOrder, setSortOrder] = useState('desc')
  const [selected, setSelected] = useState(new Set())
  const [loading, setLoading] = useState(true)
  const [deleteTarget, setDeleteTarget] = useState(null)

  const pageCount = Math.ceil(total / pageSize)

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.getExpressions(landId, {
        page, page_size: pageSize,
        min_relevance: minRelevance, max_depth: maxDepth,
        sort: sortColumn, order: sortOrder,
      })
      setExpressions(data.items || data)
      setTotal(data.total || (data.items || data).length)
    } catch (err) {
      console.error('Failed to fetch expressions:', err)
    } finally {
      setLoading(false)
    }
  }, [landId, page, pageSize, minRelevance, maxDepth, sortColumn, sortOrder])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Debounce filter changes
  useEffect(() => {
    const timer = setTimeout(() => {
      setPage(1)
      fetchData()
    }, 400)
    return () => clearTimeout(timer)
  }, [minRelevance, maxDepth])

  const toggleSelect = (id) => {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const handleSort = (col) => {
    if (col === sortColumn) {
      setSortOrder((o) => (o === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortColumn(col)
      setSortOrder('desc')
    }
  }

  const handleDeleteSelected = async () => {
    for (const id of selected) {
      try {
        await api.deleteExpression(landId, id)
      } catch {}
    }
    setSelected(new Set())
    setDeleteTarget(null)
    fetchData()
  }

  useKeyboardShortcuts([
    { key: 'ArrowLeft', action: () => page > 1 && setPage((p) => p - 1) },
    { key: 'ArrowRight', action: () => page < pageCount && setPage((p) => p + 1) },
    { key: 'd', action: () => selected.size > 0 && setDeleteTarget('batch') },
  ], [page, pageCount, selected])

  return (
    <div>
      <h4 className="mb-3">Expressions - Land #{landId}</h4>

      <div className="mb-3 p-2 bg-light rounded">
        <FilterSlider label="Relevance minimum" value={minRelevance} min={0} max={100} onChange={setMinRelevance} />
        <FilterSlider label="Profondeur max" value={maxDepth} min={0} max={10} onChange={setMaxDepth} />
      </div>

      {selected.size > 0 && (
        <div className="mb-2">
          <Button variant="danger" size="sm" onClick={() => setDeleteTarget('batch')}>
            Supprimer {selected.size} s&eacute;lectionn&eacute;(s)
          </Button>
        </div>
      )}

      {loading ? (
        <LoadingSpinner />
      ) : expressions.length === 0 ? (
        <EmptyState title="Aucune expression" message="Lancez un crawl pour extraire des expressions." />
      ) : (
        <>
          <Table hover responsive size="sm">
            <thead>
              <tr>
                <th style={{ width: 30 }}></th>
                <th style={{ cursor: 'pointer' }} onClick={() => handleSort('id')}>ID</th>
                <th style={{ cursor: 'pointer' }} onClick={() => handleSort('title')}>Titre</th>
                <th style={{ cursor: 'pointer' }} onClick={() => handleSort('domain')}>Domaine</th>
                <th style={{ cursor: 'pointer' }} onClick={() => handleSort('relevance')}>
                  Rel. {sortColumn === 'relevance' ? (sortOrder === 'asc' ? '\u2191' : '\u2193') : ''}
                </th>
                <th>Tags</th>
              </tr>
            </thead>
            <tbody>
              {expressions.map((expr) => (
                <tr
                  key={expr.id}
                  style={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/lands/${landId}/expressions/${expr.id}`)}
                >
                  <td onClick={(e) => e.stopPropagation()}>
                    <Form.Check
                      checked={selected.has(expr.id)}
                      onChange={() => toggleSelect(expr.id)}
                    />
                  </td>
                  <td>{expr.id}</td>
                  <td className="App-text-excerpt" style={{ maxWidth: 300 }}>
                    {expr.title || expr.url || '(sans titre)'}
                  </td>
                  <td className="small text-muted">{expr.domain_name || '—'}</td>
                  <td>
                    <Badge bg={expr.relevance > 50 ? 'success' : expr.relevance > 20 ? 'warning' : 'secondary'}>
                      {expr.relevance ?? '—'}
                    </Badge>
                  </td>
                  <td>{expr.tags?.length || 0}</td>
                </tr>
              ))}
            </tbody>
          </Table>
          <Pagination
            page={page}
            pageCount={pageCount}
            onPageChange={setPage}
            resultsPerPage={pageSize}
            onResultsPerPageChange={setPageSize}
          />
        </>
      )}

      <ConfirmDialog
        show={!!deleteTarget}
        title="Supprimer les expressions"
        message={`Supprimer ${selected.size} expression(s) s\u00e9lectionn\u00e9e(s) ?`}
        onConfirm={handleDeleteSelected}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}
