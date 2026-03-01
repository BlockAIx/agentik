import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { useCreateProject } from "@/hooks/use-queries"
import { Loader2, Plus } from "lucide-react"
import { useState } from "react"

const ECOSYSTEMS = ["python", "deno", "node", "go", "rust"] as const

export function CreateProjectDialog({
  onCreated,
}: {
  onCreated: (name: string) => void
}): React.JSX.Element {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState("")
  const [ecosystem, setEcosystem] = useState("python")
  const [preamble, setPreamble] = useState("")
  const [git, setGit] = useState(true)
  const mutation = useCreateProject()

  const handleSubmit = async () => {
    if (!name.trim()) return
    try {
      await mutation.mutateAsync({
        name: name.trim(),
        ecosystem,
        preamble: preamble.trim(),
        git,
      })
      setOpen(false)
      resetForm()
      onCreated(name.trim())
    } catch {
      /* mutation.error displayed in UI */
    }
  }

  const resetForm = () => {
    setName("")
    setEcosystem("python")
    setPreamble("")
    setGit(true)
    mutation.reset()
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        setOpen(v)
        if (!v) resetForm()
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm" className="h-8 gap-1.5 text-xs" aria-label="Create new project">
          <Plus className="h-3.5 w-3.5" />
          New Project
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create Project</DialogTitle>
          <DialogDescription>
            Set up a new project with a ROADMAP.json.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="project-name">Project Name</Label>
            <Input
              id="project-name"
              placeholder="my-project"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="ecosystem">Ecosystem</Label>
            <Select value={ecosystem} onValueChange={setEcosystem}>
              <SelectTrigger id="ecosystem">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ECOSYSTEMS.map((e) => (
                  <SelectItem key={e} value={e}>
                    {e}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="preamble">Description</Label>
            <Textarea
              id="preamble"
              placeholder="Brief description of the project..."
              rows={3}
              value={preamble}
              onChange={(e) => setPreamble(e.target.value)}
            />
          </div>
          <div className="flex items-center justify-between">
            <Label htmlFor="git-toggle">Git managed</Label>
            <Switch
              id="git-toggle"
              checked={git}
              onCheckedChange={setGit}
            />
          </div>
          {mutation.error && (
            <div className="p-2 bg-destructive/10 border border-destructive/20 rounded text-sm text-destructive">
              {String(mutation.error)}
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!name.trim() || mutation.isPending}>
            {mutation.isPending && <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />}
            Create
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
