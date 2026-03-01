import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useLogs } from "@/hooks/use-queries"
import { api, type LogEntry } from "@/lib/api"
import {
  AlertTriangle,
  ChevronRight,
  FileText,
  FolderOpen,
  RefreshCw,
  X,
} from "lucide-react"
import { useState } from "react"

export function Logs({
  projectName,
}: {
  projectName: string
}): React.JSX.Element {
  const { data: entries = [], isLoading, refetch } = useLogs(projectName)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [logContent, setLogContent] = useState<string | null>(null)
  const [loadingContent, setLoadingContent] = useState(false)
  const [activeLog, setActiveLog] = useState<string | null>(null)

  const handleLogClick = async (slug: string, logName: string) => {
    const key = `${slug}/${logName}`
    if (activeLog === key) return
    setActiveLog(key)
    setLoadingContent(true)
    try {
      const data = await api.getLogContent(projectName, slug, logName)
      setLogContent(data.content)
    } catch {
      setLogContent("Failed to load log content.")
    } finally {
      setLoadingContent(false)
    }
  }

  return (
    <div className="grid grid-cols-[280px_1fr] gap-4" style={{ minHeight: "50vh" }}>
      {/* Left panel — log tree */}
      <Card className="overflow-hidden">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm flex items-center gap-1.5">
            <FolderOpen className="h-3.5 w-3.5" />
            Task Logs
          </CardTitle>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-1.5"
            onClick={() => refetch()}
            disabled={isLoading}
          >
            <RefreshCw className={`h-3 w-3 ${isLoading ? "animate-spin" : ""}`} />
          </Button>
        </CardHeader>
        <CardContent className="p-0">
          <nav aria-label="Task logs" className="overflow-y-auto" style={{ maxHeight: "60vh" }}>
            {entries.length === 0 && (
              <p className="text-xs text-muted-foreground p-4 text-center">
                No logs yet.
              </p>
            )}
            {entries.map((entry) => (
              <div key={entry.task_slug} className="border-b border-border last:border-0">
                <button
                  className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm hover:bg-muted/50 transition"
                  onClick={() =>
                    setExpanded(expanded === entry.task_slug ? null : entry.task_slug)
                  }
                >
                  <ChevronRight
                    className={`h-3 w-3 shrink-0 transition-transform ${
                      expanded === entry.task_slug ? "rotate-90" : ""
                    }`}
                  />
                  <span className="truncate font-medium text-xs">{entry.task_slug}</span>
                  <Badge variant="outline" className="ml-auto text-xs shrink-0">
                    {entry.logs.length}
                  </Badge>
                  {entry.failure_report && (
                    <AlertTriangle className="h-3 w-3 text-destructive shrink-0" />
                  )}
                </button>
                {expanded === entry.task_slug && (
                  <div className="bg-muted/30">
                    {entry.logs.map((log) => {
                      const key = `${entry.task_slug}/${log.name}`
                      return (
                        <button
                          key={key}
                          className={`w-full flex items-center gap-2 px-6 py-1.5 text-left text-xs hover:bg-muted/60 transition ${
                            activeLog === key ? "bg-muted" : ""
                          }`}
                          onClick={() => handleLogClick(entry.task_slug, log.name)}
                        >
                          <FileText className="h-3 w-3 shrink-0 text-muted-foreground" />
                          <span className="truncate">{log.name}</span>
                          <span className="ml-auto text-muted-foreground text-[10px] shrink-0">
                            {(log.size / 1024).toFixed(1)}K
                          </span>
                        </button>
                      )
                    })}
                    {entry.failure_report && (
                      <FailureReport report={entry.failure_report} />
                    )}
                  </div>
                )}
              </div>
            ))}
          </nav>
        </CardContent>
      </Card>

      {/* Right panel — log viewer */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm flex items-center gap-1.5">
            <FileText className="h-3.5 w-3.5" />
            {activeLog ? activeLog.split("/").pop() : "Log Viewer"}
          </CardTitle>
          {activeLog && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-1.5"
              onClick={() => {
                setActiveLog(null)
                setLogContent(null)
              }}
            >
              <X className="h-3 w-3" />
            </Button>
          )}
        </CardHeader>
        <CardContent>
          {loadingContent ? (
            <div className="flex items-center justify-center h-40 text-muted-foreground text-sm">
              Loading...
            </div>
          ) : logContent ? (
            <pre className="text-xs font-mono whitespace-pre-wrap break-all max-h-[60vh] overflow-y-auto rounded-md bg-secondary/30 p-4 border">
              {logContent}
            </pre>
          ) : (
            <div className="flex flex-col items-center justify-center h-40 text-muted-foreground">
              <FileText className="h-8 w-8 mb-2 opacity-30" />
              <p className="text-sm">Select a log file to view.</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

/* ── Failure Report ── */

function FailureReport({
  report,
}: {
  report: NonNullable<LogEntry["failure_report"]>
}): React.JSX.Element {
  return (
    <div className="px-4 py-2 bg-destructive/5 border-t border-destructive/10">
      <div className="text-xs space-y-1">
        <div className="flex items-center gap-1.5 text-destructive font-medium">
          <AlertTriangle className="h-3 w-3" />
          Failure Report
        </div>
        <div className="text-muted-foreground">
          <span>Attempts: {report.attempts}</span>
          {report.tokens_spent > 0 && (
            <span className="ml-3">
              Tokens: {(report.tokens_spent / 1000).toFixed(1)}K
            </span>
          )}
        </div>
        {report.last_error && (
          <p className="text-destructive/80 truncate" title={report.last_error}>
            {report.last_error}
          </p>
        )}
        {report.failing_test && (
          <p className="text-muted-foreground truncate">
            Test: {report.failing_test}
          </p>
        )}
      </div>
    </div>
  )
}
