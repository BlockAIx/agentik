import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { useDiff, useHandleReview } from "@/hooks/use-queries"
import type { ProjectDetail } from "@/lib/api"
import {
  CheckCircle2,
  GitCommitHorizontal,
  Loader2,
  RefreshCw,
  XCircle,
} from "lucide-react"
import { useState } from "react"

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
              <Badge variant="default" className="bg-green-600 text-xs">
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
            <div className="p-3 bg-green-500/10 border border-green-500/20 rounded-md text-sm text-green-400">
              {result}
            </div>
          )}

          <div className="flex items-center gap-2">
            <Button
              variant="default"
              size="sm"
              className="bg-green-600 hover:bg-green-700"
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
              <Badge variant="secondary" className="text-xs font-mono">
                {diff.status || "clean"}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {diff.diff ? (
              <div
                className="overflow-y-auto rounded-md border bg-secondary/30"
                style={{ maxHeight: "50vh" }}
              >
                <pre className="p-4 text-xs font-mono whitespace-pre-wrap break-all">
                  {diff.diff.split("\n").map((line, i) => {
                    let color = ""
                    if (line.startsWith("+") && !line.startsWith("+++"))
                      color = "text-green-400"
                    else if (line.startsWith("-") && !line.startsWith("---"))
                      color = "text-red-400"
                    else if (line.startsWith("@@")) color = "text-blue-400"
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
              </div>
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
