import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { useAvailableModels, useGenerateRoadmap, useModels, useUpdateRoadmap } from "@/hooks/use-queries"
import { AlertTriangle, Check, Loader2, Sparkles, X } from "lucide-react"
import { useState } from "react"

const ECOSYSTEMS = ["python", "deno", "node", "go", "rust"] as const

export function Generator({
  projectName,
}: {
  projectName: string
}): React.JSX.Element {
  const [description, setDescription] = useState("")
  const [ecosystem, setEcosystem] = useState<string>("python")
  const [preview, setPreview] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [accepted, setAccepted] = useState(false)

  const generateMutation = useGenerateRoadmap()
  const updateMutation = useUpdateRoadmap()

  const { data: models = [] } = useModels(projectName)
  const { data: catalog = [] } = useAvailableModels()

  const architectModel = models.find((m) => m.agent === "architect")?.model ?? ""
  const architectMissing = !architectModel
  const architectInvalid =
    !architectMissing && catalog.length > 0 && !catalog.find((c) => c.full_id === architectModel)
  const architectBlocked = architectMissing || architectInvalid

  const handleGenerate = async () => {
    if (!description.trim()) return
    setError(null)
    setPreview(null)
    setAccepted(false)
    try {
      const result = await generateMutation.mutateAsync({
        name: projectName,
        description,
        ecosystem,
      })
      setPreview(JSON.stringify(result, null, 2))
    } catch (e) {
      setError(String(e))
    }
  }

  const handleAccept = async () => {
    if (!preview) return
    setError(null)
    try {
      const parsed = JSON.parse(preview)
      await updateMutation.mutateAsync({ name: projectName, data: parsed })
      setAccepted(true)
    } catch (e) {
      setError(String(e))
    }
  }

  const handleReject = () => {
    setPreview(null)
    setAccepted(false)
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-sm flex items-center gap-2">
            <Sparkles className="h-4 w-4" />
            Generate ROADMAP from Description
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Project Description</Label>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe what you want to build. Be specific about features, architecture, and requirements..."
              className="min-h-37.5 resize-y"
              disabled={generateMutation.isPending}
            />
          </div>
          <div className="flex items-end gap-4">
            <div className="space-y-2">
              <Label>Ecosystem</Label>
              <Select value={ecosystem} onValueChange={setEcosystem}>
                <SelectTrigger className="w-40">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ECOSYSTEMS.map((eco) => (
                    <SelectItem key={eco} value={eco}>
                      {eco}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button
              onClick={handleGenerate}
              disabled={generateMutation.isPending || !description.trim() || architectBlocked}
            >
              {generateMutation.isPending ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <Sparkles className="h-3.5 w-3.5 mr-1" />
                  Generate
                </>
              )}
            </Button>
          </div>
          {architectBlocked && (
            <div className="flex items-start gap-2 p-3 bg-destructive/10 border border-destructive/20 rounded-md text-sm text-destructive">
              <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
              <span>
                {architectMissing
                  ? "No architect model configured. Set one in the Models tab before generating a roadmap."
                  : "The configured architect model is not available through your connected providers. Update it in the Models tab."}
              </span>
            </div>
          )}
          {error && (
            <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md text-sm text-destructive">
              {error}
            </div>
          )}
        </CardContent>
      </Card>

      {preview && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-sm">
              Generated ROADMAP Preview
            </CardTitle>
            <div className="flex items-center gap-2">
              {accepted ? (
                <Badge variant="default" className="bg-success text-success-foreground">
                  <Check className="h-3 w-3 mr-1" />
                  Saved
                </Badge>
              ) : (
                <>
                  <Button variant="outline" size="sm" onClick={handleReject}>
                    <X className="h-3.5 w-3.5 mr-1" />
                    Discard
                  </Button>
                  <Button size="sm" onClick={handleAccept}>
                    <Check className="h-3.5 w-3.5 mr-1" />
                    Accept &amp; Save
                  </Button>
                </>
              )}
            </div>
          </CardHeader>
          <CardContent>
            <Textarea
              value={preview}
              onChange={(e) => {
                setPreview(e.target.value)
                setAccepted(false)
              }}
              className="font-mono text-xs min-h-[40vh] resize-y"
              spellCheck={false}
              readOnly={accepted}
            />
          </CardContent>
        </Card>
      )}
    </div>
  )
}
