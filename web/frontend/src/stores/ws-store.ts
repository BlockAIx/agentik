/** Zustand store — single global WebSocket connection with pub/sub. */
import { create } from "zustand"

export interface WsMessage {
  event: string
  [key: string]: unknown
}

type Listener = (msg: WsMessage) => void

interface WsState {
  connected: boolean
  /** Register a listener; returns an unsubscribe function. */
  subscribe: (listener: Listener) => () => void
  /** Open the WebSocket connection; returns a cleanup function. */
  _init: () => () => void
}

export const useWsStore = create<WsState>((set) => {
  const listeners = new Set<Listener>()

  return {
    connected: false,

    subscribe: (listener) => {
      listeners.add(listener)
      return () => {
        listeners.delete(listener)
      }
    },

    _init: () => {
      let disposed = false
      let ws: WebSocket | null = null
      let reconnectTimer: ReturnType<typeof setTimeout> | null = null

      function open() {
        if (disposed) return
        const proto = location.protocol === "https:" ? "wss:" : "ws:"
        ws = new WebSocket(`${proto}//${location.host}/ws`)

        ws.onopen = () => {
          set({ connected: true })
          const ping = setInterval(() => {
            if (ws?.readyState === WebSocket.OPEN) ws.send("ping")
          }, 30_000)
          ws!.onclose = () => {
            clearInterval(ping)
            set({ connected: false })
            if (!disposed) reconnectTimer = setTimeout(open, 3_000)
          }
        }

        ws.onmessage = (e) => {
          try {
            const msg = JSON.parse(e.data) as WsMessage
            if (msg.event !== "pong") {
              for (const fn of listeners) fn(msg)
            }
          } catch {
            /* ignore non-JSON frames */
          }
        }

        ws.onerror = () => ws?.close()
      }

      open()
      return () => {
        disposed = true
        if (reconnectTimer) clearTimeout(reconnectTimer)
        ws?.close()
      }
    },
  }
})
