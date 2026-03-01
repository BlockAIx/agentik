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
  const [validateMsg, setValidateMsg] = useState<string | null>(null)

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
    setValidateMsg(null)
    try {
      const res = await validateMutation.mutateAsync(projectName)
      setValidateMsg(res.valid ? "ROADMAP is valid" : "Validation returned issues")
    } catch (e) {
      setValidateMsg(`Validation error: ${e}`)
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between py-3">
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
              onChange={(v) => setLocalContent(v ?? "")}
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
        <div className="p-3 bg-green-500/10 border border-green-500/20 rounded-md text-sm text-green-400 flex items-start gap-2">
          <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
          {saveMsg}
        </div>
      )}
      {validateMsg && (
        <div
          className={`p-3 border rounded-md text-sm flex items-start gap-2 ${
            validateMsg.includes("valid")
              ? "bg-green-500/10 border-green-500/20 text-green-400"
              : "bg-yellow-500/10 border-yellow-500/20 text-yellow-400"
          }`}
        >
          <ShieldCheck className="h-4 w-4 shrink-0 mt-0.5" />
          {validateMsg}
        </div>
      )}
    </div>
  )
}
