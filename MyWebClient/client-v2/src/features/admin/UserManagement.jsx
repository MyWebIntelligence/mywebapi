import { useState, useEffect, useCallback } from 'react'
import { Table, Button, Badge, Form, InputGroup, Alert, Modal } from 'react-bootstrap'
import * as adminApi from '../../api/adminApi'
import Pagination from '../../components/Pagination'
import LoadingSpinner from '../../components/LoadingSpinner'
import ConfirmDialog from '../../components/ConfirmDialog'

export default function UserManagement() {
  const [users, setUsers] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState(null)
  const [actionTarget, setActionTarget] = useState(null)
  const [actionType, setActionType] = useState(null)
  const [tempPassword, setTempPassword] = useState(null)

  const fetchUsers = useCallback(async () => {
    setLoading(true)
    try {
      const data = await adminApi.getUsers({ page, page_size: pageSize, search: search || undefined })
      setUsers(data.items || [])
      setTotal(data.total || 0)
    } catch (err) {
      setMessage({ type: 'danger', text: 'Erreur chargement utilisateurs' })
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, search])

  useEffect(() => {
    fetchUsers()
  }, [fetchUsers])

  const doAction = async () => {
    if (!actionTarget || !actionType) return
    try {
      let result
      switch (actionType) {
        case 'block':
          await adminApi.blockUser(actionTarget.id)
          break
        case 'unblock':
          await adminApi.unblockUser(actionTarget.id)
          break
        case 'promote':
          await adminApi.setRole(actionTarget.id, { is_admin: true })
          break
        case 'demote':
          await adminApi.setRole(actionTarget.id, { is_admin: false })
          break
        case 'reset-password':
          result = await adminApi.forceResetPassword(actionTarget.id)
          setTempPassword(result.temporary_password)
          break
        case 'delete':
          await adminApi.deleteUser(actionTarget.id)
          break
      }
      setMessage({ type: 'success', text: `Action "${actionType}" effectu\u00e9e` })
      fetchUsers()
    } catch (err) {
      setMessage({ type: 'danger', text: err.response?.data?.detail || 'Erreur' })
    } finally {
      setActionTarget(null)
      setActionType(null)
    }
  }

  const confirmAction = (user, type) => {
    setActionTarget(user)
    setActionType(type)
  }

  const pageCount = Math.ceil(total / pageSize)

  return (
    <div>
      <h4 className="mb-3">Gestion des utilisateurs</h4>

      {message && (
        <Alert variant={message.type} dismissible onClose={() => setMessage(null)}>{message.text}</Alert>
      )}

      <InputGroup className="mb-3" size="sm">
        <Form.Control
          placeholder="Rechercher..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1) }}
        />
      </InputGroup>

      {loading ? (
        <LoadingSpinner />
      ) : (
        <>
          <Table hover responsive size="sm">
            <thead>
              <tr>
                <th>ID</th>
                <th>Username</th>
                <th>Email</th>
                <th>R&ocirc;le</th>
                <th>Statut</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.id}</td>
                  <td>{u.username}</td>
                  <td className="small">{u.email || '—'}</td>
                  <td>
                    <Badge bg={u.is_admin ? 'warning' : 'secondary'}>
                      {u.is_admin ? 'admin' : 'user'}
                    </Badge>
                  </td>
                  <td>
                    <Badge bg={u.is_active ? 'success' : 'danger'}>
                      {u.is_active ? 'actif' : 'inactif'}
                    </Badge>
                  </td>
                  <td>
                    <div className="d-flex gap-1 flex-wrap">
                      {u.is_active ? (
                        <Button size="sm" variant="outline-warning" onClick={() => confirmAction(u, 'block')}>
                          Bloquer
                        </Button>
                      ) : (
                        <Button size="sm" variant="outline-success" onClick={() => confirmAction(u, 'unblock')}>
                          D&eacute;bloquer
                        </Button>
                      )}
                      {u.is_admin ? (
                        <Button size="sm" variant="outline-secondary" onClick={() => confirmAction(u, 'demote')}>
                          Retirer admin
                        </Button>
                      ) : (
                        <Button size="sm" variant="outline-info" onClick={() => confirmAction(u, 'promote')}>
                          Admin
                        </Button>
                      )}
                      <Button size="sm" variant="outline-primary" onClick={() => confirmAction(u, 'reset-password')}>
                        Reset MDP
                      </Button>
                      <Button size="sm" variant="outline-danger" onClick={() => confirmAction(u, 'delete')}>
                        Supprimer
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
          <Pagination page={page} pageCount={pageCount} onPageChange={setPage} />
        </>
      )}

      <ConfirmDialog
        show={!!actionTarget && !!actionType}
        title={`Confirmer: ${actionType}`}
        message={`Voulez-vous ${actionType} l'utilisateur "${actionTarget?.username}" ?`}
        confirmText="Confirmer"
        confirmVariant={actionType === 'delete' ? 'danger' : 'primary'}
        onConfirm={doAction}
        onCancel={() => { setActionTarget(null); setActionType(null) }}
      />

      <Modal show={!!tempPassword} onHide={() => setTempPassword(null)} centered>
        <Modal.Header closeButton>
          <Modal.Title>Mot de passe temporaire</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Alert variant="warning">
            <strong>Mot de passe temporaire:</strong>
            <code className="d-block mt-2 p-2 bg-light">{tempPassword}</code>
            <small>Communiquez ce mot de passe &agrave; l'utilisateur de mani&egrave;re s&eacute;curis&eacute;e.</small>
          </Alert>
        </Modal.Body>
      </Modal>
    </div>
  )
}
