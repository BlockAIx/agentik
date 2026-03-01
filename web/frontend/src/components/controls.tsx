import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import {
  useInvalidateProject,
  usePipelineStatus,
  useRunPipeline,
  useStopPipeline,
} from "@/hooks/use-queries"
import type { ProjectDetail } from "@/lib/api"
import { useWsStore } from "@/stores/ws-store"
import {
  AlertTriangle,
  Loader2,
  Play,
  RefreshCw,
  Square,
  Trash2,
} from "lucide-react"
import { useCallback, useEffect, useRef, useState } from "react"

const MAX_LOG_LINES = 2000

export function Controls({
  projectName,
  detail,
  invalidModels,
}: {
  projectName: string
  detail: ProjectDetail
  invalidModels?: Array<{ agent: string; model: string }>
}): React.JSX.Element {
  const [logs, setLogs] = useState<string[]>([])
  const [verbose, setVerbose] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const logContainerRef = useRef<HTMLDivElement>(null)

  const { data: pipeStatus } = usePipelineStatus()
  const pipelineActive = pipeStatus?.running ?? false
  const statusChecked = pipeStatus !== undefined

  const runMutation = useRunPipeline()
  const stopMutation = useStopPipeline()
  const invalidate = useInvalidateProject()

  /* WS subscription for live log lines + pipeline events */
  const handleWs = useCallback(
    (msg: { event: string; [k: string]: unknown }) => {
      if (msg.event === "pipeline_started" && msg.project === projectName) {
        setLogs([])
      } else if (msg.event === "pipeline_stopped" && msg.project === projectName) {
        invalidate(projectName)
      } else if (msg.event === "log_line" && msg.project === projectName) {
        setLogs((prev) => {
          const next = [...prev, msg.line as string]
          return next.length > MAX_LOG_LINES ? next.slice(-MAX_LOG_LINES) : next
        })
      }
    },
    [projectName, invalidate],
  )

  useEffect(() => useWsStore.getState().subscribe(handleWs), [handleWs])

  useEffect(() => {
    const el = logContainerRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [logs])

  const handleRun = async () => {
    setMessage(null)
    try {
      const res = await runMutation.mutateAsync({ name: projectName, verbose })
      if (!res.started) setMessage("Pipeline already running")
    } catch {
      /* mutation state has error */
    }
  }

  const handleStop = async () => {
    setMessage(null)
    try {
      const res = await stopMutation.mutateAsync(projectName)
      setMessage(res.stopped ? "Stop signal sent" : "Pipeline was not running")
    } catch {
      /* mutation state has error */
    }
  }

  const error = runMutation.error ?? stopMutation.error
  const { state } = detail

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Pipeline Controls</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-3 flex-wrap">
            <Button
              onClick={handleRun}
              disabled={
                runMutation.isPending ||
                pipelineActive ||
                !statusChecked ||
                (invalidModels?.length ?? 0) > 0
              }
            >
              {runMutation.isPending ? (
                <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
              ) : (
                <Play className="h-3.5 w-3.5 mr-1" />
              )}
              Run Pipeline
            </Button>
            <Button
              variant="destructive"
              onClick={handleStop}
              disabled={stopMutation.isPending || !pipelineActive || !statusChecked}
            >
              {stopMutation.isPending ? (
                <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
              ) : (
                <Square className="h-3.5 w-3.5 mr-1" />
              )}
              Stop
            </Button>
            <Button variant="outline" onClick={() => invalidate(projectName)}>
              <RefreshCw className="h-3.5 w-3.5 mr-1" />
              Refresh
            </Button>
            <label className="flex items-center gap-1.5 text-sm text-muted-foreground cursor-pointer select-none">
              <input
                type="checkbox"
                checked={verbose}
                onChange={(e) => setVerbose(e.target.checked)}
                className="rounded"
              />
              Verbose
            </label>
            {pipelineActive && (
              <Badge
                variant="outline"
                className="gap-1 text-success border-success/30 animate-pulse"
              >
                <Loader2 className="h-3 w-3 animate-spin" />
                Running
              </Badge>
            )}
          </div>

          {invalidModels && invalidModels.length > 0 && (
            <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md text-sm text-destructive flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
              <div>
                <p className="font-medium">
                  Model configuration invalid — cannot run pipeline
                </p>
                <ul className="mt-1 space-y-0.5">
                  {invalidModels.map((m) => (
                    <li key={m.agent} className="text-xs font-mono">
                      {m.agent}: {m.model}
                    </li>
                  ))}
                </ul>
                <p className="mt-1 text-xs text-muted-foreground">
                  Go to the Models tab to update them.
                </p>
              </div>
            </div>
          )}

          {error && (
            <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md text-sm text-destructive">
              {String(error)}
            </div>
          )}
          {message && (
            <div className="p-3 bg-success/10 border border-success/20 rounded-md text-sm text-success">
              {message}
            </div>
          )}

          <Separator />

          <div className="grid grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">Current Task</span>
              <div className="mt-1 font-medium">
                {state.current_task ? (
                  <Badge variant="outline">{state.current_task}</Badge>
                ) : (
                  <span className="text-muted-foreground">&mdash;</span>
                )}
              </div>
            </div>
            <div>
              <span className="text-muted-foreground">Attempt</span>
              <div className="mt-1 font-medium">
                {state.attempt || "\u2014"}
              </div>
            </div>
            <div>
              <span className="text-muted-foreground">Progress</span>
              <div className="mt-1 font-medium">
                {state.completed} / {state.total}
              </div>
            </div>
            <div>
              <span className="text-muted-foreground">Failures</span>
              <div className="mt-1 font-medium">
                {state.failed.length > 0 ? (
                  <Badge variant="destructive">{state.failed.length}</Badge>
                ) : (
                  <Badge variant="secondary">0</Badge>
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Live log output panel */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm">Live Pipeline Output</CardTitle>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setLogs([])}
            className="h-6 px-2 text-xs"
          >
            <Trash2 className="h-3 w-3 mr-1" />
            Clear
          </Button>
        </CardHeader>
        <CardContent className="p-0">
          <div ref={logContainerRef} className="bg-terminal rounded-b-lg font-mono text-xs text-terminal-foreground h-115 overflow-y-auto p-3 border-t border-border">
            {logs.length === 0 ? (
              <span className="text-terminal-muted">
                {pipelineActive
                  ? "Starting pipeline..."
                  : "No output yet — click Run Pipeline to start."}
              </span>
            ) : (
              logs.map((line, i) => (
                <div
                  key={i}
                  className="leading-5 whitespace-pre-wrap break-all"
                >
                  {line}
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
