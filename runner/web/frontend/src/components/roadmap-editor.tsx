import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Save, CheckCircle2, AlertTriangle, RotateCcw } from "lucide-react";
import { api } from "@/lib/api";

export function RoadmapEditor({ projectName }: { projectName: string }) {
  const [content, setContent] = useState("");
  const [original, setOriginal] = useState("");
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  const [valid, setValid] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);

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
      // Validate JSON syntax first.
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
        <Textarea
          value={content}
          onChange={(e) => {
            setContent(e.target.value);
            setValid(null);
          }}
          className="font-mono text-xs min-h-[60vh] resize-y"
          spellCheck={false}
        />
      </CardContent>
    </Card>
  );
}
