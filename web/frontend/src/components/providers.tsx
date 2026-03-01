import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import {
  useAvailableModels,
  useProviderLogin,
  useProviderLogout,
  useProviders,
  useRefreshModels,
} from "@/hooks/use-queries"
import type { AvailableModel, ProviderInfo } from "@/lib/api"
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Key,
  Loader2,
  LogIn,
  LogOut,
  RefreshCw,
  Search,
  Server,
  Terminal,
  Zap,
} from "lucide-react"
import { useState } from "react"

/** Shape returned by /api/providers/login. */
interface LoginGuide {
  success: boolean
  in_docker: boolean
  is_windows: boolean
  github_token_set: boolean
  login_command: string
  note: string
  steps: string[]
  alternatives: Array<{
    title: string
    description: string
    env_var: string
    docs_url: string
  }>
}

export function Providers(): React.JSX.Element {
  const {
    data: providerData,
    isLoading: loadingProviders,
    refetch: refetchProviders,
  } = useProviders()
  const { data: models = [], isLoading: loadingModels } = useAvailableModels()

  const loginMutation = useProviderLogin()
  const logoutMutation = useProviderLogout()
  const refreshMutation = useRefreshModels()

  const providers: ProviderInfo[] = providerData?.providers ?? []

  const [loginGuide, setLoginGuide] = useState<LoginGuide | null>(null)
  const [showAlternatives, setShowAlternatives] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [modelFilter, setModelFilter] = useState("")

  const handleLogin = async () => {
    if (loginGuide) {
      setLoginGuide(null)
      setShowAlternatives(false)
      return
    }
    setError(null)
    try {
      const result = await loginMutation.mutateAsync(undefined)
      setLoginGuide(result)
    } catch (e) {
      setError(String(e))
    }
  }

  const handleLogout = async () => {
    setError(null)
    try {
      await logoutMutation.mutateAsync()
    } catch (e) {
      setError(String(e))
    }
  }

  const handleRefreshModels = async () => {
    try {
      await refreshMutation.mutateAsync()
    } catch (e) {
      setError(String(e))
    }
  }

  const handleRefreshAll = async () => {
    await refetchProviders()
    await handleRefreshModels()
  }

  const grouped = models.reduce<Record<string, AvailableModel[]>>((acc, m) => {
    if (!acc[m.provider]) acc[m.provider] = []
    acc[m.provider].push(m)
    return acc
  }, {})

  const filtered = modelFilter.trim()
    ? models.filter((m) =>
        m.full_id.toLowerCase().includes(modelFilter.toLowerCase()),
      )
    : null

  const hasGithubCopilot = providers.some(
    (p) =>
      p.name.toLowerCase().includes("github copilot") ||
      p.name.toLowerCase().includes("copilot"),
  )

  return (
    <div className="space-y-6">
      {/* ── Connection status ── */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm flex items-center gap-2">
            <Key className="h-4 w-4" />
            Connected Providers
          </CardTitle>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetchProviders()}
            disabled={loadingProviders}
          >
            <RefreshCw
              className={`h-3.5 w-3.5 mr-1 ${loadingProviders ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && (
            <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md text-sm text-destructive flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              {error}
            </div>
          )}

          {loadingProviders ? (
            <div className="flex items-center justify-center py-6">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : providers.length === 0 ? (
            <div className="text-center py-6 space-y-3">
              <p className="text-sm text-muted-foreground">
                No providers connected. Log in to start using models.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {providers.map((p, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between p-3 rounded-md border border-border bg-card"
                >
                  <div className="flex items-center gap-3">
                    <div className="h-8 w-8 rounded-full bg-success/10 flex items-center justify-center">
                      <CheckCircle2 className="h-4 w-4 text-success" />
                    </div>
                    <div>
                      <p className="text-sm font-medium">{p.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {p.auth_type} · {p.source}
                      </p>
                    </div>
                  </div>
                  <Badge
                    variant="outline"
                    className="text-success border-success/30 text-xs"
                  >
                    Connected
                  </Badge>
                </div>
              ))}
            </div>
          )}

          <Separator />

          {/* Login / Logout */}
          <div className="flex items-center gap-3">
            {!hasGithubCopilot ? (
              <Button
                onClick={handleLogin}
                disabled={loginMutation.isPending}
                size="sm"
                variant={loginGuide ? "secondary" : "default"}
              >
                <LogIn className="h-3.5 w-3.5 mr-1.5" />
                {loginMutation.isPending
                  ? "Loading..."
                  : loginGuide
                    ? "Hide instructions"
                    : "Connect GitHub Copilot"}
              </Button>
            ) : (
              <Button
                onClick={handleLogin}
                disabled={loginMutation.isPending}
                variant={loginGuide ? "secondary" : "outline"}
                size="sm"
              >
                <LogIn className="h-3.5 w-3.5 mr-1.5" />
                {loginMutation.isPending
                  ? "Loading..."
                  : loginGuide
                    ? "Hide instructions"
                    : "Add Provider"}
              </Button>
            )}
            {providers.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleLogout}
                disabled={logoutMutation.isPending}
                className="text-muted-foreground hover:text-destructive"
              >
                <LogOut className="h-3.5 w-3.5 mr-1.5" />
                {logoutMutation.isPending ? "Logging out..." : "Logout"}
              </Button>
            )}
          </div>

          {loginGuide && (
            <ConnectGuide
              guide={loginGuide}
              showAlternatives={showAlternatives}
              onToggleAlternatives={() => setShowAlternatives((v) => !v)}
              onRefresh={handleRefreshAll}
            />
          )}

          <p className="text-xs text-muted-foreground">
            GitHub Copilot uses OAuth device flow — run the login command in your
            terminal and follow the on-screen steps. API providers (Anthropic,
            OpenAI) use environment variables (
            <code className="bg-muted px-1 rounded text-xs">
              ANTHROPIC_API_KEY
            </code>
            ,{" "}
            <code className="bg-muted px-1 rounded text-xs">
              OPENAI_API_KEY
            </code>
            ).
          </p>
        </CardContent>
      </Card>

      {/* ── Available models ── */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm flex items-center gap-2">
            <Zap className="h-4 w-4" />
            Available Models
            {!loadingModels && (
              <Badge variant="secondary" className="text-xs">
                {models.length}
              </Badge>
            )}
          </CardTitle>
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefreshModels}
            disabled={refreshMutation.isPending}
          >
            <RefreshCw
              className={`h-3.5 w-3.5 mr-1 ${refreshMutation.isPending ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          {loadingModels ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : models.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-6">
              No models available. Connect a provider first.
            </p>
          ) : (
            <>
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
                <Input
                  placeholder="Filter models..."
                  value={modelFilter}
                  onChange={(e) => setModelFilter(e.target.value)}
                  className="pl-8 h-8 text-xs"
                />
              </div>

              <div className="max-h-100 overflow-y-auto pr-1">
                {filtered ? (
                  <div className="space-y-1">
                    {filtered.map((m) => (
                      <ModelRow key={m.full_id} model={m} />
                    ))}
                    {filtered.length === 0 && (
                      <p className="text-xs text-muted-foreground text-center py-4">
                        No models match &ldquo;{modelFilter}&rdquo;
                      </p>
                    )}
                  </div>
                ) : (
                  <div className="space-y-4">
                    {Object.entries(grouped).map(([provider, provModels]) => (
                      <div key={provider}>
                        <div className="flex items-center gap-2 mb-2">
                          <Server className="h-3.5 w-3.5 text-muted-foreground" />
                          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                            {provider}
                          </span>
                          <Badge variant="outline" className="text-xs">
                            {provModels.length}
                          </Badge>
                        </div>
                        <div className="space-y-1">
                          {provModels.map((m) => (
                            <ModelRow key={m.full_id} model={m} />
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}

          <p className="text-xs text-muted-foreground">
            These are the models available through your connected providers. Use
            the model ID (e.g.{" "}
            <code className="bg-muted px-1 rounded text-xs">
              github-copilot/claude-sonnet-4
            </code>
            ) in the project Models tab to assign models to agents.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}

/* ── Connection guide ── */

function ConnectGuide({
  guide,
  showAlternatives,
  onToggleAlternatives,
  onRefresh,
}: {
  guide: LoginGuide
  showAlternatives: boolean
  onToggleAlternatives: () => void
  onRefresh: () => void
}): React.JSX.Element {
  const [cmdCopied, setCmdCopied] = useState(false)

  const copyCmd = () => {
    navigator.clipboard
      .writeText(guide.login_command)
      .then(() => {
        setCmdCopied(true)
        setTimeout(() => setCmdCopied(false), 1800)
      })
      .catch(() => {})
  }

  return (
    <div className="rounded-md border border-info/20 bg-info/5 space-y-4 p-4">
      <div className="flex items-center gap-2">
        <Terminal className="h-4 w-4 text-info" />
        <p className="text-sm font-medium">How to connect</p>
        {guide.in_docker && (
          <Badge
            variant="outline"
            className="text-xs text-info border-info/30"
          >
            Docker
          </Badge>
        )}
      </div>

      <p className="text-xs text-muted-foreground">{guide.note}</p>

      <div className="flex items-center gap-2">
        <code className="flex-1 text-xs font-mono bg-muted rounded px-3 py-2 break-all">
          {guide.login_command}
        </code>
        <Button
          size="sm"
          variant="outline"
          className="shrink-0 h-8 text-xs"
          onClick={copyCmd}
        >
          {cmdCopied ? "Copied!" : "Copy"}
        </Button>
      </div>

      <ol className="space-y-1.5 pl-1">
        {guide.steps.map((step, i) => (
          <li
            key={i}
            className="flex items-start gap-2 text-xs text-muted-foreground"
          >
            <span className="shrink-0 h-4 w-4 rounded-full bg-muted flex items-center justify-center text-[10px] font-medium mt-0.5">
              {i + 1}
            </span>
            <StepText text={step} />
          </li>
        ))}
      </ol>

      <a
        href="https://github.com/login/device"
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1.5 text-xs text-info hover:underline"
      >
        <ExternalLink className="h-3 w-3" />
        github.com/login/device
      </a>

      <div className="flex items-center gap-3 pt-1">
        <Button
          size="sm"
          variant="outline"
          onClick={onRefresh}
          className="gap-1.5"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh status
        </Button>
        <span className="text-xs text-muted-foreground">
          Click after completing auth in the terminal
        </span>
      </div>

      <Separator />

      <button
        className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
        onClick={onToggleAlternatives}
      >
        {showAlternatives ? (
          <ChevronDown className="h-3 w-3" />
        ) : (
          <ChevronRight className="h-3 w-3" />
        )}
        Alternative: use API keys via environment variables
      </button>

      {showAlternatives && (
        <div className="space-y-3">
          {guide.alternatives.map((alt) => (
            <div
              key={alt.env_var}
              className="rounded border border-border p-3 space-y-1.5"
            >
              <div className="flex items-center justify-between">
                <p className="text-xs font-medium">{alt.title}</p>
                <a
                  href={alt.docs_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
                >
                  <ExternalLink className="h-3 w-3" />
                  Get key
                </a>
              </div>
              <p className="text-xs text-muted-foreground">
                {alt.description}
              </p>
              <code className="text-xs font-mono bg-muted px-2 py-1 rounded block">
                {alt.env_var}=sk-...
              </code>
            </div>
          ))}
          <p className="text-xs text-muted-foreground">
            Add these to your{" "}
            <code className="bg-muted px-1 rounded">.env</code> file at the
            workspace root, then restart the server for them to take effect.
          </p>
        </div>
      )}
    </div>
  )
}

/** Renders a step string, turning **bold** and `code` into styled spans. */
function StepText({ text }: { text: string }): React.JSX.Element {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g)
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return (
            <strong key={i} className="text-foreground">
              {part.slice(2, -2)}
            </strong>
          )
        }
        if (part.startsWith("`") && part.endsWith("`")) {
          return (
            <code key={i} className="bg-muted px-1 rounded text-foreground">
              {part.slice(1, -1)}
            </code>
          )
        }
        return <span key={i}>{part}</span>
      })}
    </>
  )
}

/* ── Model row ── */

function ModelRow({ model }: { model: AvailableModel }): React.JSX.Element {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard
      .writeText(model.full_id)
      .then(() => {
        setCopied(true)
        setTimeout(() => setCopied(false), 1500)
      })
      .catch(() => {})
  }

  return (
    <div
      className="flex items-center justify-between px-3 py-1.5 rounded hover:bg-muted/50 cursor-pointer group"
      onClick={handleCopy}
      title="Click to copy model ID"
    >
      <span className="text-xs font-mono flex-1 truncate">
        {model.full_id}
      </span>
      <div className="flex items-center gap-2 shrink-0 ml-2">
        <span
          className={`text-xs transition-opacity ${
            copied
              ? "text-success opacity-100"
              : "text-muted-foreground opacity-0 group-hover:opacity-100"
          }`}
        >
          {copied ? "Copied!" : "Copy"}
        </span>
      </div>
    </div>
  )
}
