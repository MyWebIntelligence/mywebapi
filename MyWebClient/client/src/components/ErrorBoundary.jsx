import { Component } from 'react'
import { Alert, Button } from 'react-bootstrap'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-4">
          <Alert variant="danger">
            <Alert.Heading>Une erreur est survenue</Alert.Heading>
            <p>{this.state.error?.message || 'Erreur inattendue'}</p>
            <Button
              variant="outline-danger"
              onClick={() => this.setState({ hasError: false, error: null })}
            >
              R&eacute;essayer
            </Button>
          </Alert>
        </div>
      )
    }

    return this.props.children
  }
}
