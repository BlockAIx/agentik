import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { ErrorBoundary } from "./error-boundary"

afterEach(cleanup)

function Thrower({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) throw new Error("test boom")
  return <div>OK</div>
}

describe("ErrorBoundary", () => {
  it("renders children when no error", () => {
    render(
      <ErrorBoundary>
        <Thrower shouldThrow={false} />
      </ErrorBoundary>,
    )
    expect(screen.getByText("OK")).toBeInTheDocument()
  })

  it("renders error UI on throw", () => {
    // suppress console.error from React error boundary
    const spy = vi.spyOn(console, "error").mockImplementation(() => {})
    render(
      <ErrorBoundary>
        <Thrower shouldThrow={true} />
      </ErrorBoundary>,
    )
    expect(screen.getByText("Something went wrong")).toBeInTheDocument()
    expect(screen.getByText("test boom")).toBeInTheDocument()
    expect(screen.getByText("Try again")).toBeInTheDocument()
    spy.mockRestore()
  })
})
