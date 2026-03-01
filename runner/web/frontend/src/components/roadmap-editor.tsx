import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import Editor, { type BeforeMount } from "@monaco-editor/react";
import { AlertTriangle, CheckCircle2, RotateCcw, Save } from "lucide-react";
import type { editor } from "monaco-editor";
import { useCallback, useEffect, useRef, useState } from "react";

export function RoadmapEditor({ projectName }: { projectName: string }) {
  const [content, setContent] = useState("");
  const [original, setOriginal] = useState("");
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  const [valid, setValid] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);

  /** Configure JSON diagnostics & schema before editor mounts. */
  const handleBeforeMount: BeforeMount = useCallback((monaco) => {
    monaco.languages.json.jsonDefaults.setDiagnosticsOptions({
      validate: true,
      allowComments: false,
      trailingCommas: "error",
      schemaValidation: "error",
      schemas: [
        {
          uri: "https://agentik.dev/schemas/roadmap.json",
          fileMatch: ["*"],
          schema: {
            type: "object",
            required: ["name", "ecosystem", "tasks"],
            properties: {
              name: { type: "string", description: "Project name" },
              ecosystem: {
                type: "string",
                enum: ["python", "deno", "node", "rust", "go", "ruby"],
                description: "Project ecosystem",
              },
              preamble: { type: "string", description: "Brief project description" },
              git: {
                type: "object",
                properties: { enabled: { type: "boolean" } },
                additionalProperties: false,
              },
              review: { type: "boolean" },
              min_coverage: { type: "number", minimum: 0, maximum: 100 },
              notify: {
                type: "object",
                properties: {
                  url: { type: "string", format: "uri" },
                  events: {
                    type: "array",
                    items: {
                      type: "string",
                      enum: ["task_complete", "task_failed", "pipeline_done"],
                    },
                  },
                },
              },
              deploy: {
                type: "object",
                properties: {
                  enabled: { type: "boolean" },
                  script: { type: "string" },
                  env: { type: "object" },
                },
              },
              tasks: {
                type: "array",
                items: {
                  type: "object",
                  required: ["id", "title", "depends_on"],
                  properties: {
                    id: { type: "integer", minimum: 1 },
                    title: { type: "string", maxLength: 80 },
                    agent: {
                      type: "string",
                      enum: ["build", "fix", "test", "document", "explore", "plan", "architect", "milestone"],
                    },
                    ecosystem: {
                      type: "string",
                      enum: ["python", "deno", "node", "rust", "go", "ruby"],
                    },
                    depends_on: {
                      type: "array",
                      items: { type: "integer", minimum: 1 },
                    },
                    context: {
                      type: "array",
                      items: { type: "string" },
                    },
                    outputs: {
                      type: "array",
                      items: { type: "string" },
                    },
                    acceptance: { type: "string" },
                    version: { type: "string" },
                    deploy: { type: "boolean" },
                    description: { type: "string" },
                  },
                  additionalProperties: false,
                },
              },
            },
            additionalProperties: false,
          },
        },
      ],
    });
  }, []);

  useEffect(() => {
    api
      .getRoadmap(projectName)
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
    try {
      const parsed = JSON.parse(content);
      const result = await api.updateRoadmap(projectName, parsed);
      setValid(result.valid);
      setOriginal(content);
    } catch (e) {
      setError(e instanceof SyntaxError ? `Invalid JSON: ${e.message}` : String(e));
    } finally {
      setSaving(false);
    }
  };

  const handleValidate = async () => {
    setValidating(true);
    setError(null);
    try {
      JSON.parse(content);
      const result = await api.validateRoadmap(projectName);
      setValid(result.valid);
    } catch (e) {
      if (e instanceof SyntaxError) {
        setError(`Invalid JSON: ${e.message}`);
        setValid(false);
      } else {
        setError(String(e));
      }
    } finally {
      setValidating(false);
    }
  };

  const isDirty = content !== original;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-sm flex items-center gap-2">
          ROADMAP.json
          {isDirty && (
            <Badge variant="secondary" className="text-xs">
              Unsaved changes
            </Badge>
          )}
          {valid === true && (
            <Badge variant="default" className="bg-green-600 text-xs">
              <CheckCircle2 className="h-3 w-3 mr-1" />
              Valid
            </Badge>
          )}
          {valid === false && (
            <Badge variant="destructive" className="text-xs">
              <AlertTriangle className="h-3 w-3 mr-1" />
              Invalid
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
              setValid(null);
              setError(null);
            }}
          >
            <RotateCcw className="h-3.5 w-3.5 mr-1" />
            Reset
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleValidate}
            disabled={validating}
          >
            {validating ? "Validating..." : "Validate"}
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
            height="60vh"
            language="json"
            theme="vs-dark"
            value={content}
            beforeMount={handleBeforeMount}
            onChange={(value) => {
              setContent(value ?? "");
              setValid(null);
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
