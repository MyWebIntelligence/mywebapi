import { useState, useEffect, useCallback } from 'react'
import { Row, Col, Button, Form, InputGroup } from 'react-bootstrap'
import * as landsApi from '../../api/landsApi'
import LandCard from './LandCard'
import LandForm from './LandForm'
import ConfirmDialog from '../../components/ConfirmDialog'
import LoadingSpinner from '../../components/LoadingSpinner'
import EmptyState from '../../components/EmptyState'
import Pagination from '../../components/Pagination'

export default function LandList() {
  const [lands, setLands] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editLand, setEditLand] = useState(null)
  const [deleteLand, setDeleteLand] = useState(null)

  const fetchLands = useCallback(async () => {
    setLoading(true)
    try {
      const data = await landsApi.getLands({ page, pageSize, nameFilter: search })
      setLands(data.items || data)
      setTotal(data.total || (data.items || data).length)
    } catch (err) {
      console.error('Failed to fetch lands:', err)
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, search])

  useEffect(() => {
    fetchLands()
  }, [fetchLands])

  const handleCreate = () => {
    setEditLand(null)
    setShowForm(true)
  }

  const handleEdit = (land) => {
    setEditLand(land)
    setShowForm(true)
  }

  const handleSave = async (data) => {
    try {
      if (editLand?.id) {
        await landsApi.updateLand(editLand.id, data)
      } else {
        await landsApi.createLand(data)
      }
      setShowForm(false)
      fetchLands()
    } catch (err) {
      console.error('Failed to save land:', err)
    }
  }

  const handleDelete = async () => {
    if (!deleteLand) return
    try {
      await landsApi.deleteLand(deleteLand.id)
      setDeleteLand(null)
      fetchLands()
    } catch (err) {
      console.error('Failed to delete land:', err)
    }
  }

  const pageCount = Math.ceil(total / pageSize)

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h4 className="mb-0">Projets (Lands)</h4>
        <Button variant="primary" size="sm" onClick={handleCreate}>
          + Nouveau projet
        </Button>
      </div>

      <InputGroup className="mb-3" size="sm">
        <Form.Control
          placeholder="Rechercher par nom..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(1)
          }}
        />
      </InputGroup>

      {loading ? (
        <LoadingSpinner />
      ) : lands.length === 0 ? (
        <EmptyState
          title="Aucun projet"
          message="Cr\u00e9ez votre premier projet pour commencer."
          action={
            <Button variant="primary" size="sm" onClick={handleCreate}>
              Cr&eacute;er un projet
            </Button>
          }
        />
      ) : (
        <>
          <Row xs={1} md={2} lg={3} className="g-3 mb-3">
            {lands.map((land) => (
              <Col key={land.id}>
                <LandCard
                  land={land}
                  onEdit={handleEdit}
                  onDelete={setDeleteLand}
                />
              </Col>
            ))}
          </Row>
          <Pagination page={page} pageCount={pageCount} onPageChange={setPage} />
        </>
      )}

      <LandForm
        show={showForm}
        land={editLand}
        onSave={handleSave}
        onClose={() => setShowForm(false)}
      />

      <ConfirmDialog
        show={!!deleteLand}
        title="Supprimer le projet"
        message={`Voulez-vous vraiment supprimer "${deleteLand?.name || deleteLand?.title}" ? Cette action est irr\u00e9versible.`}
        confirmText="Supprimer"
        onConfirm={handleDelete}
        onCancel={() => setDeleteLand(null)}
      />
    </div>
  )
}
