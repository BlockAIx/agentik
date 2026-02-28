import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { Check, Loader2, Sparkles, X } from "lucide-react";
import { useState } from "react";

const ECOSYSTEMS = ["python", "deno", "node", "go", "rust"] as const;

export function Generator({ projectName }: { projectName: string }) {
  const [description, setDescription] = useState("");
  const [ecosystem, setEcosystem] = useState<string>("python");
  const [generating, setGenerating] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [accepted, setAccepted] = useState(false);

  const handleGenerate = async () => {
    if (!description.trim()) return;
    setGenerating(true);
    setError(null);
    setPreview(null);
    setAccepted(false);
    try {
      const result = await api.generateRoadmap(
        projectName,
        description,
        ecosystem
      );
      setPreview(JSON.stringify(result, null, 2));
    } catch (e) {
      setError(String(e));
    } finally {
      setGenerating(false);
    }
  };

  const handleAccept = async () => {
    if (!preview) return;
    setError(null);
    try {
      const parsed = JSON.parse(preview);
      await api.updateRoadmap(projectName, parsed);
      setAccepted(true);
    } catch (e) {
      setError(String(e));
    }
  };

  const handleReject = () => {
    setPreview(null);
    setAccepted(false);
  };

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
              className="min-h-[150px] resize-y"
              disabled={generating}
            />
          </div>
          <div className="flex items-end gap-4">
            <div className="space-y-2">
              <Label>Ecosystem</Label>
              <Select value={ecosystem} onValueChange={setEcosystem}>
                <SelectTrigger className="w-[160px]">
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
              disabled={generating || !description.trim()}
            >
              {generating ? (
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
            <CardTitle className="text-sm">Generated ROADMAP Preview</CardTitle>
            <div className="flex items-center gap-2">
              {accepted ? (
                <Badge variant="default" className="bg-green-600">
                  <Check className="h-3 w-3 mr-1" />
                  Saved
                </Badge>
              ) : (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleReject}
                  >
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
                setPreview(e.target.value);
                setAccepted(false);
              }}
              className="font-mono text-xs min-h-[40vh] resize-y"
              spellCheck={false}
              readOnly={accepted}
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
