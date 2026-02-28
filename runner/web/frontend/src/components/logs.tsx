import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { FileText, AlertTriangle, ChevronRight } from "lucide-react";
import { api } from "@/lib/api";
import type { LogEntry } from "@/lib/api";

export function Logs({ projectName }: { projectName: string }) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [selectedLog, setSelectedLog] = useState<string | null>(null);
  const [logContent, setLogContent] = useState<string>("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.getLogs(projectName).then(setLogs).catch(console.error);
  }, [projectName]);

  const loadLog = async (slug: string, name: string) => {
    setSelectedSlug(slug);
    setSelectedLog(name);
    setLoading(true);
    try {
      const data = await api.getLogContent(projectName, slug, name);
      setLogContent(data.content);
    } catch (e) {
      setLogContent(`Error loading log: ${e}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
      {/* Log tree */}
      <Card className="lg:col-span-1">
        <CardHeader>
          <CardTitle className="text-sm">Task Logs</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <ScrollArea className="h-[60vh]">
            {logs.length === 0 && (
              <p className="p-4 text-sm text-muted-foreground">
                No logs yet.
              </p>
            )}
            {logs.map((entry) => (
              <div key={entry.task_slug} className="px-3 py-2">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <FileText className="h-3 w-3" />
                  {entry.task_slug}
                  {entry.failure_report && (
                    <AlertTriangle className="h-3 w-3 text-destructive" />
                  )}
                </div>
                <div className="ml-5 mt-1 space-y-0.5">
                  {entry.logs.map((log) => (
                    <button
                      key={log.name}
                      onClick={() => loadLog(entry.task_slug, log.name)}
                      className={`flex items-center gap-1 text-xs w-full text-left px-2 py-1 rounded hover:bg-accent transition-colors ${
                        selectedSlug === entry.task_slug &&
                        selectedLog === log.name
                          ? "bg-accent text-accent-foreground"
                          : "text-muted-foreground"
                      }`}
                    >
                      <ChevronRight className="h-3 w-3" />
                      {log.name}
                      <span className="ml-auto">
                        {(log.size / 1024).toFixed(1)}K
                      </span>
                    </button>
                  ))}
                  {entry.failure_report && (
                    <button
                      onClick={() => {
                        setSelectedSlug(entry.task_slug);
                        setSelectedLog("failure_report");
                        setLogContent(
                          JSON.stringify(entry.failure_report, null, 2),
                        );
                      }}
                      className={`flex items-center gap-1 text-xs w-full text-left px-2 py-1 rounded hover:bg-destructive/20 transition-colors ${
                        selectedSlug === entry.task_slug &&
                        selectedLog === "failure_report"
                          ? "bg-destructive/20 text-destructive-foreground"
                          : "text-destructive"
                      }`}
                    >
                      <AlertTriangle className="h-3 w-3" />
                      failure_report.json
                    </button>
                  )}
                </div>
                <Separator className="mt-2" />
              </div>
            ))}
          </ScrollArea>
        </CardContent>
      </Card>

      {/* Log viewer */}
      <Card className="lg:col-span-3">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm">
            {selectedLog
              ? `${selectedSlug}/${selectedLog}`
              : "Select a log file"}
          </CardTitle>
          {selectedLog && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setSelectedSlug(null);
                setSelectedLog(null);
                setLogContent("");
              }}
            >
              Clear
            </Button>
          )}
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center h-40 text-muted-foreground">
              Loading...
            </div>
          ) : selectedLog === "failure_report" && selectedSlug ? (
            <FailureReport
              report={
                logs.find((l) => l.task_slug === selectedSlug)
                  ?.failure_report ?? null
              }
            />
          ) : logContent ? (
            <ScrollArea className="h-[60vh]">
              <pre className="text-xs font-mono whitespace-pre-wrap p-4 bg-secondary rounded-md">
                {logContent}
              </pre>
            </ScrollArea>
          ) : (
            <div className="flex items-center justify-center h-40 text-muted-foreground">
              Select a log file to view its contents.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function FailureReport({
  report,
}: {
  report: {
    task: string;
    attempts: number;
    last_error: string | null;
    failing_test: string | null;
    tokens_spent: number;
    timestamp: string;
  } | null;
}) {
  if (!report) return null;

  return (
    <div className="space-y-4">
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertTitle>Task Failed</AlertTitle>
        <AlertDescription>{report.task}</AlertDescription>
      </Alert>

      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <span className="text-muted-foreground">Attempts:</span>
          <span className="ml-2 font-medium">{report.attempts}</span>
        </div>
        <div>
          <span className="text-muted-foreground">Tokens spent:</span>
          <span className="ml-2 font-medium">{report.tokens_spent}</span>
        </div>
        <div className="col-span-2">
          <span className="text-muted-foreground">Timestamp:</span>
          <span className="ml-2 font-medium">{report.timestamp}</span>
        </div>
      </div>

      {report.failing_test && (
        <div>
          <h4 className="text-sm font-medium mb-1">Failing Test</h4>
          <Badge variant="destructive">{report.failing_test}</Badge>
        </div>
      )}

      {report.last_error && (
        <div>
          <h4 className="text-sm font-medium mb-1">Error</h4>
          <pre className="text-xs font-mono p-3 bg-destructive/10 rounded-md whitespace-pre-wrap border border-destructive/20">
            {report.last_error}
          </pre>
        </div>
      )}
    </div>
  );
}
