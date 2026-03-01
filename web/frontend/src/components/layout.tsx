/** Shared Layout shell — header, nav, WS status badge. */
import { CreateProjectDialog } from "@/components/create-project"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { useWsStore } from "@/stores/ws-store"
import { ArrowLeft, Settings2, Wifi, WifiOff } from "lucide-react"
import { Link, useNavigate } from "react-router-dom"

interface LayoutProps {
  children: React.ReactNode
  title?: string
  /** Navigate to a fixed path when the back button is clicked. */
  backTo?: string
  backLabel?: string
  /** When true, back button calls history.back() instead of navigating to a fixed path. */
  historyBack?: boolean
  badge?: React.ReactNode
  onCreated?: (name: string) => void
}

export function Layout({
  children,
  title,
  backTo,
  backLabel,
  historyBack = false,
  badge,
  onCreated,
}: LayoutProps): React.JSX.Element {
  const connected = useWsStore((s) => s.connected)
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {(backTo ?? historyBack) ? (
              <>
                {historyBack ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 px-2 gap-1.5 text-xs"
                    onClick={() => navigate(-1)}
                  >
                    <ArrowLeft className="h-3.5 w-3.5" />
                    {backLabel ?? "Back"}
                  </Button>
                ) : (
                  <Link to={backTo!}>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 px-2 gap-1.5 text-xs"
                    >
                      <ArrowLeft className="h-3.5 w-3.5" />
                      {backLabel ?? "Back"}
                    </Button>
                  </Link>
                )}
                <Separator orientation="vertical" className="h-5" />
              </>
            ) : (
              <Link
                to="/"
                className="text-lg font-semibold tracking-tight hover:opacity-80 transition"
              >
                agentik
              </Link>
            )}
            {title && (
              <h1 className="text-lg font-semibold tracking-tight">
                {title}
              </h1>
            )}
            {badge}
            {onCreated && (
              <>
                <Separator orientation="vertical" className="h-5" />
                <CreateProjectDialog onCreated={onCreated} />
              </>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Link to="/settings">
              <Button
                variant="ghost"
                size="sm"
                className="h-8 px-2 text-xs gap-1.5"
              >
                <Settings2 className="h-3.5 w-3.5" />
                {!backTo && "Settings"}
              </Button>
            </Link>
            {connected ? (
              <Badge
                variant="outline"
                className="gap-1 text-green-500 border-green-500/30"
              >
                <Wifi className="h-3 w-3" />
                Live
              </Badge>
            ) : (
              <Badge
                variant="outline"
                className="gap-1 text-muted-foreground"
              >
                <WifiOff className="h-3 w-3" />
                Offline
              </Badge>
            )}
          </div>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 py-6">{children}</main>
    </div>
  )
}
