import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { useDiff, useHandleReview } from "@/hooks/use-queries"
import type { ProjectDetail } from "@/lib/api"
import { cn } from "@/lib/utils"
import {
  CheckCircle2,
  GitCommitHorizontal,
  Loader2,
  RefreshCw,
  XCircle,
} from "lucide-react"
import { useState } from "react"

interface StatusFile {
  marker: string
  file: string
}

function parseStatusFiles(status: string): StatusFile[] {
  return status
    .split("\n")
    .filter((l) => l.trim().length > 0)
    .map((l) => {
      const marker = l.slice(0, 2).trim()
      let file = l.slice(3).trim()
      // Renames: "old -> new" — use the destination path for diff lookup
      if (marker.startsWith("R") && file.includes(" -> ")) {
        file = file.split(" -> ")[1].trim()
      }
      return { marker, file }
    })
}

function markerColor(marker: string): string {
  if (marker === "M" || marker === "MM") return "text-warning"
  if (marker === "A" || marker === "AM") return "text-success"
  if (marker === "D") return "text-destructive"
  if (marker === "R") return "text-info"
  if (marker === "??") return "text-muted-foreground"
  return "text-foreground"
}

function splitDiffByFile(raw: string): Record<string, string> {
  const out: Record<string, string> = {}
  const chunks = raw.split(/(?=^diff --git )/m)
  for (const chunk of chunks) {
    if (!chunk.trim()) continue
    const m = chunk.match(/^diff --git a\/.+ b\/(.+)$/m)
    if (m) out[m[1].trim()] = chunk
  }
  return out
}

export function Review({
  projectName,
  detail,
}: {
  projectName: string
  detail: ProjectDetail
}): React.JSX.Element {
  const { data: diff, isLoading, refetch } = useDiff(projectName)
  const reviewMutation = useHandleReview()
  const [result, setResult] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selectedFile, setSelectedFile] = useState<string | null>(null)

  const handleAction = async (action: "approve" | "reject") => {
    setError(null)
    setResult(null)
    try {
      const res = await reviewMutation.mutateAsync({ name: projectName, action })
      setResult(
        res.acknowledged
          ? `Review ${action}d successfully`
          : `Action sent: ${action}`,
      )
    } catch (e) {
      setError(String(e))
    }
  }

  const currentTask = detail.state.current_task
  const reviewEnabled = detail.review_enabled

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm flex items-center gap-2">
            <GitCommitHorizontal className="h-4 w-4" />
            Code Review
            {reviewEnabled ? (
              <Badge variant="default" className="bg-success text-success-foreground text-xs">
                Enabled
              </Badge>
            ) : (
              <Badge variant="secondary" className="text-xs">
                Disabled
              </Badge>
            )}
          </CardTitle>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isLoading}
          >
            <RefreshCw
              className={`h-3.5 w-3.5 mr-1 ${isLoading ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
        </CardHeader>
        <CardContent className="space-y-4">
          {currentTask ? (
            <div className="text-sm">
              Current task:{" "}
              <Badge variant="outline">{currentTask}</Badge>
              <span className="ml-2 text-muted-foreground">
                Attempt {detail.state.attempt}
              </span>
            </div>
          ) : (
            <div className="text-sm text-muted-foreground">
              No task currently in progress.
            </div>
          )}

          {error && (
            <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md text-sm text-destructive">
              {error}
            </div>
          )}
          {result && (
            <div className="p-3 bg-success/10 border border-success/20 rounded-md text-sm text-success">
              {result}
            </div>
          )}

          <div className="flex items-center gap-2">
            <Button
              variant="default"
              size="sm"
              className="bg-success hover:bg-success/80 text-success-foreground"
              onClick={() => handleAction("approve")}
              disabled={reviewMutation.isPending || !reviewEnabled}
            >
              {reviewMutation.isPending ? (
                <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
              ) : (
                <CheckCircle2 className="h-3.5 w-3.5 mr-1" />
              )}
              Approve
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => handleAction("reject")}
              disabled={reviewMutation.isPending || !reviewEnabled}
            >
              {reviewMutation.isPending ? (
                <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
              ) : (
                <XCircle className="h-3.5 w-3.5 mr-1" />
              )}
              Reject
            </Button>
          </div>
        </CardContent>
      </Card>

      {diff && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2">
              Git Diff
              {(() => {
                const files = parseStatusFiles(diff.status)
                return files.length > 0 ? (
                  <Badge variant="secondary" className="text-xs">
                    {files.length} file{files.length > 1 ? "s" : ""} changed
                  </Badge>
                ) : (
                  <Badge variant="secondary" className="text-xs">clean</Badge>
                )
              })()}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {diff.diff ? (
              (() => {
                const files = parseStatusFiles(diff.status)
                const byFile = splitDiffByFile(diff.diff)
                const activeContent: string | null = selectedFile
                  ? (byFile[selectedFile] ?? null)
                  : diff.diff
                return (
                  <div className="flex rounded-md border overflow-hidden" style={{ maxHeight: "55vh" }}>
                    {/* File list sidebar */}
                    {files.length > 0 && (
                      <div className="w-52 shrink-0 border-r overflow-y-auto">
                        <button
                          type="button"
                          onClick={() => setSelectedFile(null)}
                          className={cn(
                            "w-full text-left px-3 py-1.5 text-xs font-medium border-b transition-colors",
                            selectedFile === null
                              ? "bg-secondary text-foreground"
                              : "text-muted-foreground hover:bg-secondary/50",
                          )}
                        >
                          All files
                        </button>
                        {files.map(({ marker, file }) => (
                          <button
                            key={file}
                            type="button"
                            onClick={() => setSelectedFile(file === selectedFile ? null : file)}
                            className={cn(
                              "w-full text-left px-3 py-1.5 flex items-start gap-1.5 transition-colors",
                              selectedFile === file
                                ? "bg-secondary"
                                : "hover:bg-secondary/50",
                            )}
                          >
                            <span className={cn("text-xs font-mono font-bold shrink-0 mt-0.5 w-4", markerColor(marker))}>
                              {marker || "?"}
                            </span>
                            <span className="text-xs font-mono break-all leading-tight text-foreground">
                              {file.includes("/")
                                ? file.split("/").slice(-1)[0]
                                : file}
                            </span>
                          </button>
                        ))}
                      </div>
                    )}
                    {/* Diff content */}
                    <div className="flex-1 overflow-auto">
                      {activeContent === null ? (
                        <div className="h-full flex items-center justify-center text-xs text-muted-foreground p-8 text-center">
                          No diff available for this file.
                        </div>
                      ) : (
                      <pre className="p-4 text-xs font-mono whitespace-pre-wrap break-all">
                        {activeContent.split("\n").map((line, i) => {
                          let color = ""
                          if (line.startsWith("+") && !line.startsWith("+++"))
                            color = "text-success"
                          else if (line.startsWith("-") && !line.startsWith("---"))
                            color = "text-destructive"
                          else if (line.startsWith("@@")) color = "text-info"
                          else if (
                            line.startsWith("diff ") ||
                            line.startsWith("index ")
                          )
                            color = "text-muted-foreground"
                          return (
                            <span key={i} className={color}>
                              {line}
                              {"\n"}
                            </span>
                          )
                        })}
                      </pre>
                      )}
                    </div>
                  </div>
                )
              })()
            ) : (
              <div className="text-sm text-muted-foreground p-4 text-center">
                No changes detected.
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {!reviewEnabled && (
        <>
          <Separator />
          <p className="text-xs text-muted-foreground">
            Review mode is disabled. Enable it in ROADMAP.json by setting{" "}
            <code className="bg-muted px-1 rounded">&quot;review&quot;: true</code>{" "}
            at the top level.
          </p>
        </>
      )}
    </div>
  )
}
