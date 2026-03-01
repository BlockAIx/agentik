import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import Editor from "@monaco-editor/react";
import { AlertTriangle, CheckCircle2, Coins, RotateCcw, Save } from "lucide-react";
import type { editor } from "monaco-editor";
import { useEffect, useRef, useState } from "react";

export function BudgetEditor({ projectName }: { projectName: string }) {
  const [content, setContent] = useState("");
  const [original, setOriginal] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);

  useEffect(() => {
    api
      .getProjectBudget(projectName)
      .then((data) => {
        const text = JSON.stringify(data, null, 2);
        setContent(text);
        setOriginal(text);
      })
      .catch((e) => setError(String(e)));
  }, [projectName]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const parsed = JSON.parse(content);
      await api.updateProjectBudget(projectName, parsed);
      setSaved(true);
      setOriginal(content);
    } catch (e) {
      setError(
        e instanceof SyntaxError ? `Invalid JSON: ${e.message}` : String(e),
      );
    } finally {
      setSaving(false);
    }
  };

  const isDirty = content !== original;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-sm flex items-center gap-2">
          <Coins className="h-4 w-4" />
          budget.json
          {isDirty && (
            <Badge variant="secondary" className="text-xs">
              Unsaved changes
            </Badge>
          )}
          {saved && !isDirty && (
            <Badge variant="default" className="bg-green-600 text-xs">
              <CheckCircle2 className="h-3 w-3 mr-1" />
              Saved
            </Badge>
          )}
          {error && (
            <Badge variant="destructive" className="text-xs">
              <AlertTriangle className="h-3 w-3 mr-1" />
              Error
            </Badge>
          )}
        </CardTitle>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={!isDirty}
            onClick={() => {
              setContent(original);
              setError(null);
              setSaved(false);
            }}
          >
            <RotateCcw className="h-3.5 w-3.5 mr-1" />
            Reset
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={saving || !isDirty}
          >
            <Save className="h-3.5 w-3.5 mr-1" />
            {saving ? "Saving..." : "Save"}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {error && (
          <div className="mb-3 p-3 bg-destructive/10 border border-destructive/20 rounded-md text-sm text-destructive">
            {error}
          </div>
        )}
        <div className="border border-border rounded-md overflow-hidden">
          <Editor
            height="40vh"
            language="json"
            theme="vs-dark"
            value={content}
            onChange={(value) => {
              setContent(value ?? "");
              setSaved(false);
            }}
            onMount={(editor) => {
              editorRef.current = editor;
            }}
            options={{
              minimap: { enabled: false },
              fontSize: 13,
              lineNumbers: "on",
              scrollBeyondLastLine: false,
              wordWrap: "on",
              tabSize: 2,
              formatOnPaste: true,
              automaticLayout: true,
              bracketPairColorization: { enabled: true },
              folding: true,
              renderValidationDecorations: "on",
            }}
          />
        </div>
      </CardContent>
    </Card>
  );
}
