import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import type { ProjectDetail } from "@/lib/api";
import { api } from "@/lib/api";
import { CheckCircle2, GitCommitHorizontal, Loader2, RefreshCw, XCircle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

interface DiffData {
  diff: string;
  status: string;
}

export function Review({
  projectName,
  detail,
}: {
  projectName: string;
  detail: ProjectDetail;
}) {
  const [diff, setDiff] = useState<DiffData | null>(null);
  const [loading, setLoading] = useState(false);
  const [acting, setActing] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchDiff = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getDiff(projectName);
      setDiff(data);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [projectName]);

  useEffect(() => {
    fetchDiff();
  }, [fetchDiff]);

  const handleAction = async (action: "approve" | "reject") => {
    setActing(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.handleReview(projectName, action);
      setResult(
        res.acknowledged
          ? `Review ${action}d successfully`
          : `Action sent: ${action}`
      );
    } catch (e) {
      setError(String(e));
    } finally {
      setActing(false);
    }
  };

  const currentTask = detail.state.current_task;
  const reviewEnabled = detail.review_enabled;

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
          <Button variant="outline" size="sm" onClick={fetchDiff} disabled={loading}>
            <RefreshCw className={`h-3.5 w-3.5 mr-1 ${loading ? "animate-spin" : ""}`} />
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
              disabled={acting || !reviewEnabled}
            >
              {acting ? (
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
              disabled={acting || !reviewEnabled}
            >
              {acting ? (
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
              <ScrollArea className="h-[50vh] rounded-md border">
                <pre className="p-4 text-xs font-mono whitespace-pre overflow-x-auto">
                  {diff.diff.split("\n").map((line, i) => {
                    let color = "";
                    if (line.startsWith("+") && !line.startsWith("+++")) {
                      color = "text-green-400";
                    } else if (line.startsWith("-") && !line.startsWith("---")) {
                      color = "text-red-400";
                    } else if (line.startsWith("@@")) {
                      color = "text-blue-400";
                    } else if (line.startsWith("diff ") || line.startsWith("index ")) {
                      color = "text-muted-foreground";
                    }
                    return (
                      <span key={i} className={color}>
                        {line}
                        {"\n"}
                      </span>
                    );
                  })}
                </pre>
              </ScrollArea>
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
            <code className="bg-muted px-1 rounded">"review": true</code> at
            the top level.
          </p>
        </>
      )}
    </div>
  );
}
