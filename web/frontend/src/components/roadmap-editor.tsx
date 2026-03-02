import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useRoadmap, useUpdateRoadmap, useValidateRoadmap } from "@/hooks/use-queries"
import Editor, { type BeforeMount } from "@monaco-editor/react"
import {
    AlertTriangle,
    CheckCircle2,
    FileCode2,
    Loader2,
    Save,
    ShieldCheck,
} from "lucide-react"
import { useState } from "react"

type ValidationResult = {
  valid: boolean
  errors: Array<{ task: string; message: string }>
  warnings: Array<{ task: string; message: string }>
}

export function RoadmapEditor({
  projectName,
}: {
  projectName: string
}): React.JSX.Element {
  const { data: roadmapData } = useRoadmap(projectName)
  const updateMutation = useUpdateRoadmap()
  const validateMutation = useValidateRoadmap()

  const [localContent, setLocalContent] = useState<string | null>(null)
  const [parseError, setParseError] = useState<string | null>(null)
  const [saveMsg, setSaveMsg] = useState<string | null>(null)
  const [validateResult, setValidateResult] = useState<ValidationResult | null>(null)

  const baseContent = roadmapData ? JSON.stringify(roadmapData, null, 2) : ""
  const content = localContent ?? baseContent
  const isDirty = localContent !== null

  /** Configure Monaco JSON defaults before mount. */
  const handleBeforeMount: BeforeMount = (monaco) => {
    monaco.languages.json.jsonDefaults.setDiagnosticsOptions({
      validate: true,
      allowComments: false,
      trailingCommas: "error",
      schemaValidation: "warning",
      schemas: [
        {
          uri: "https://agentik.dev/roadmap.schema.json",
          fileMatch: ["*"],
          schema: {
            type: "object",
            required: ["name", "ecosystem", "tasks"],
            properties: {
              name: { type: "string" },
              ecosystem: {
                type: "string",
                enum: ["python", "deno", "node", "go", "rust"],
              },
              preamble: { type: "string" },
              git: {
                type: "object",
                properties: { enabled: { type: "boolean" } },
              },
              tasks: {
                type: "array",
                items: {
                  type: "object",
                  required: ["id", "title", "depends_on"],
                  properties: {
                    id: { type: "integer" },
                    title: { type: "string" },
                    depends_on: { type: "array", items: { type: "integer" } },
                    agent: { type: "string" },
                    context: { type: "array", items: { type: "string" } },
                    outputs: { type: "array", items: { type: "string" } },
                    acceptance: { type: "string" },
                    description: { type: "string" },
                  },
                },
              },
            },
          },
        },
      ],
    })
  }

  const handleSave = async () => {
    setParseError(null)
    setSaveMsg(null)
    let parsed: Record<string, unknown>
    try {
      parsed = JSON.parse(content)
    } catch (e) {
      setParseError(e instanceof Error ? e.message : "Invalid JSON")
      return
    }
    try {
      await updateMutation.mutateAsync({ name: projectName, data: parsed })
      setLocalContent(null)
      setSaveMsg("Saved successfully")
    } catch (e) {
      setParseError(String(e))
    }
  }

  const handleValidate = async () => {
    setValidateResult(null)
    try {
      const res = await validateMutation.mutateAsync(projectName)
      setValidateResult(res)
    } catch (e) {
      setParseError(`Validation error: ${e}`)
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm flex items-center gap-1.5">
            <FileCode2 className="h-4 w-4" />
            ROADMAP.json
          </CardTitle>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleValidate}
              disabled={validateMutation.isPending}
            >
              {validateMutation.isPending ? (
                <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
              ) : (
                <ShieldCheck className="h-3.5 w-3.5 mr-1" />
              )}
              Validate
            </Button>
            <Button
              size="sm"
              onClick={handleSave}
              disabled={!isDirty || updateMutation.isPending}
            >
              {updateMutation.isPending ? (
                <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
              ) : (
                <Save className="h-3.5 w-3.5 mr-1" />
              )}
              Save
            </Button>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="border-t" style={{ height: "60vh" }}>
            <Editor
              defaultLanguage="json"
              value={content}
              onChange={(v: string | undefined) => setLocalContent(v ?? "")}
              beforeMount={handleBeforeMount}
              theme="vs-dark"
              options={{
                minimap: { enabled: false },
                fontSize: 13,
                lineNumbers: "on",
                scrollBeyondLastLine: false,
                wordWrap: "on",
                tabSize: 2,
                formatOnPaste: true,
              }}
            />
          </div>
        </CardContent>
      </Card>

      {/* Status messages */}
      {parseError && (
        <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md text-sm text-destructive flex items-start gap-2">
          <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
          {parseError}
        </div>
      )}
      {saveMsg && (
        <div className="p-3 bg-success/10 border border-success/20 rounded-md text-sm text-success flex items-start gap-2">
          <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
          {saveMsg}
        </div>
      )}
      {validateResult && validateResult.valid && validateResult.warnings.length === 0 && (
        <div className="p-3 bg-success/10 border border-success/20 rounded-md text-sm text-success flex items-start gap-2">
          <ShieldCheck className="h-4 w-4 shrink-0 mt-0.5" />
          All checks passed — ROADMAP is valid.
        </div>
      )}
      {validateResult && (validateResult.errors.length > 0 || validateResult.warnings.length > 0) && (
        <div className="space-y-2">
          {validateResult.errors.length > 0 && (
            <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md text-sm text-destructive">
              <div className="flex items-center gap-2 font-medium mb-2">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                {validateResult.errors.length} error{validateResult.errors.length > 1 ? "s" : ""}
              </div>
              <ul className="space-y-1 pl-6 list-disc">
                {validateResult.errors.map((e, i) => (
                  <li key={i}>
                    <span className="font-mono text-xs">task {e.task}</span>
                    {" — "}
                    {e.message}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {validateResult.warnings.length > 0 && (
            <div className="p-3 bg-warning/10 border border-warning/20 rounded-md text-sm text-warning-foreground">
              <div className="flex items-center gap-2 font-medium mb-2">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                {validateResult.warnings.length} warning{validateResult.warnings.length > 1 ? "s" : ""}
              </div>
              <ul className="space-y-1 pl-6 list-disc">
                {validateResult.warnings.map((w, i) => (
                  <li key={i}>
                    <span className="font-mono text-xs">task {w.task}</span>
                    {" — "}
                    {w.message}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
