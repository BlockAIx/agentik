import { useCallback, useEffect, useRef, useState } from "react"

interface WsMessage {
  event: string
  [key: string]: unknown
}

export function useWebSocket(onMessage?: (msg: WsMessage) => void) {
  const wsRef = useRef<WebSocket | null>(null)
  const [connected, setConnected] = useState(false)

  const connect = useCallback(() => {
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
        setTimeout(connect, 3000)
      }
    }

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data) as WsMessage
        if (data.event !== "pong" && onMessage) {
          onMessage(data)
        }
      } catch {
        // Ignore non-JSON messages.
      }
    }

    ws.onerror = () => {
      ws.close()
    }

    wsRef.current = ws
  }, [onMessage])

  useEffect(() => {
    connect()
    return () => {
      wsRef.current?.close()
    }
  }, [connect])

  return { connected }
}
