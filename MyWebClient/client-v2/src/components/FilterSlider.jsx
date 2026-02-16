import { Form } from 'react-bootstrap'

export default function FilterSlider({ label, value, min = 0, max = 100, step = 1, onChange }) {
  return (
    <Form.Group className="mb-2">
      <Form.Label className="d-flex justify-content-between mb-0">
        <small>{label}</small>
        <small className="text-muted">{value}</small>
      </Form.Label>
      <Form.Range
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </Form.Group>
  )
}
