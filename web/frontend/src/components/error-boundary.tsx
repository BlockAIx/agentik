import { Component } from "react"

interface Props {
  children: React.ReactNode
  fallback?: React.ReactNode
}
interface State {
  error: Error | null
}

/** Return true when the error is a stale-chunk dynamic-import failure. */
function isChunkLoadError(error: Error): boolean {
  return (
    error.name === "TypeError" &&
    /failed to fetch dynamically imported module|loading chunk|loading css chunk/i.test(
      error.message,
    )
  )
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    // Stale build chunk — reload once to pick up the new index.html.
    if (isChunkLoadError(error)) {
      window.location.reload()
    }
    return { error }
  }

  render(): React.ReactNode {
    if (this.state.error) {
      // While a chunk-load reload is in flight, show the spinner instead of an
      // error screen so the user sees a seamless transition.
      if (isChunkLoadError(this.state.error)) {
        return (
          <div className="min-h-screen flex items-center justify-center bg-background">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        )
      }
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
