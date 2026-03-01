import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { useWsStore } from "./ws-store"

describe("ws-store", () => {
  beforeEach(() => {
    // Reset store state between tests
    useWsStore.setState({ connected: false })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("starts disconnected", () => {
    expect(useWsStore.getState().connected).toBe(false)
  })

  it("subscribe returns an unsubscribe function", () => {
    const listener = vi.fn()
    const unsub = useWsStore.getState().subscribe(listener)
    expect(typeof unsub).toBe("function")
    unsub()
  })

  it("_init returns a cleanup function", () => {
    // Mock WebSocket with a real constructor function
    const closeFn = vi.fn()
    function MockWebSocket() {
      return {
        onopen: null,
        onclose: null,
        onmessage: null,
        onerror: null,
        close: closeFn,
        send: vi.fn(),
        readyState: 1,
      }
    }
    MockWebSocket.OPEN = 1
    MockWebSocket.CLOSED = 3
    vi.stubGlobal("WebSocket", MockWebSocket)

    const cleanup = useWsStore.getState()._init()
    expect(typeof cleanup).toBe("function")
    cleanup()
    expect(closeFn).toHaveBeenCalled()

    vi.unstubAllGlobals()
  })
})
