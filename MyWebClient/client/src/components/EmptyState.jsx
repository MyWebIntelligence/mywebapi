export default function EmptyState({ title = 'Aucun résultat', message, action }) {
  return (
    <div className="text-center text-muted py-5">
      <h5>{title}</h5>
      {message && <p>{message}</p>}
      {action}
    </div>
  )
}
