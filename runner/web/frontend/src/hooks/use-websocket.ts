import { useEffect, useRef, useState } from "react"

export interface WsMessage {
  event: string
  [key: string]: unknown
}

export function useWebSocket(onMessage?: (msg: WsMessage) => void) {
  const wsRef = useRef<WebSocket | null>(null)
  const [connected, setConnected] = useState(false)

  // Store callback in a ref so changing it never triggers a reconnect.
  const onMessageRef = useRef(onMessage)
  useEffect(() => {
    onMessageRef.current = onMessage
  }, [onMessage])

  useEffect(() => {
    let disposed = false
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null

    function openConnection() {
      if (disposed) return

      const proto = window.location.protocol === "https:" ? "wss:" : "ws:"
      const url = `${proto}//${window.location.host}/ws`
      const ws = new WebSocket(url)

      ws.onopen = () => {
        setConnected(true)
        // Ping every 30s to keep alive.
        const interval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send("ping")
        }, 30000)
        ws.onclose = () => {
          clearInterval(interval)
          setConnected(false)
          // Auto-reconnect after 3s.
          if (!disposed) {
            reconnectTimer = setTimeout(openConnection, 3000)
          }
        }
      }

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data) as WsMessage
          if (data.event !== "pong" && onMessageRef.current) {
            onMessageRef.current(data)
          }
        } catch {
          // Ignore non-JSON messages.
        }
      }

      ws.onerror = () => {
        ws.close()
      }

      wsRef.current = ws
    }

    openConnection()

    return () => {
      disposed = true
      if (reconnectTimer) clearTimeout(reconnectTimer)
      wsRef.current?.close()
    }
  }, [])

  return { connected }
}
