import { Pagination as BSPagination, Form } from 'react-bootstrap'

export default function Pagination({ page, pageCount, onPageChange, resultsPerPage, onResultsPerPageChange }) {
  return (
    <div className="d-flex align-items-center justify-content-between flex-wrap gap-2">
      <BSPagination className="mb-0" size="sm">
        <BSPagination.Prev disabled={page <= 1} onClick={() => onPageChange(page - 1)} />
        <BSPagination.Item active>{page} / {pageCount || 1}</BSPagination.Item>
        <BSPagination.Next disabled={page >= pageCount} onClick={() => onPageChange(page + 1)} />
      </BSPagination>
      {onResultsPerPageChange && (
        <Form.Select
          size="sm"
          style={{ width: 'auto' }}
          value={resultsPerPage}
          onChange={(e) => onResultsPerPageChange(Number(e.target.value))}
        >
          <option value={25}>25</option>
          <option value={50}>50</option>
          <option value={100}>100</option>
        </Form.Select>
      )}
    </div>
  )
}
