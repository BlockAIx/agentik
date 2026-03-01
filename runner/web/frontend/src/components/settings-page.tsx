import { GlobalConfig } from "@/components/settings"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { useWebSocket } from "@/hooks/use-websocket"
import { ArrowLeft, Settings2, Wifi, WifiOff } from "lucide-react"
import { Link } from "react-router-dom"

/**
 * Global settings page at /settings — budget limits, token prices, and
 * runner configuration. Project-specific settings (models) live inside
 * each project view.
 */
export function SettingsPage(): React.JSX.Element {
  const { connected } = useWebSocket()

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link to="/">
              <Button variant="ghost" size="sm" className="h-8 px-2 gap-1.5 text-xs">
                <ArrowLeft className="h-3.5 w-3.5" />
                Dashboard
              </Button>
            </Link>
            <Separator orientation="vertical" className="h-5" />
            <h1 className="text-lg font-semibold tracking-tight flex items-center gap-2">
              <Settings2 className="h-5 w-5" />
              Global Settings
            </h1>
          </div>
          <div className="flex items-center gap-2">
            {connected ? (
              <Badge variant="outline" className="gap-1 text-green-500 border-green-500/30">
                <Wifi className="h-3 w-3" />
                Live
              </Badge>
            ) : (
              <Badge variant="outline" className="gap-1 text-muted-foreground">
                <WifiOff className="h-3 w-3" />
                Offline
              </Badge>
            )}
          </div>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 py-6">
        <GlobalConfig />
      </main>
    </div>
  )
}
