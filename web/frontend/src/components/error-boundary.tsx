/** ErrorBoundary — catches render errors with a retry button. */
import { Component } from "react"

interface Props {
  children: React.ReactNode
  fallback?: React.ReactNode
}
interface State {
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  render(): React.ReactNode {
    if (this.state.error) {
      if (this.props.fallback) return this.props.fallback
      return (
        <div className="min-h-screen flex items-center justify-center bg-background">
          <div className="text-center space-y-4 p-8">
            <h2 className="text-lg font-semibold text-destructive">
              Something went wrong
            </h2>
            <pre className="text-xs text-muted-foreground max-w-md overflow-auto">
              {this.state.error.message}
            </pre>
            <button
              className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm"
              onClick={() => this.setState({ error: null })}
            >
              Try again
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
