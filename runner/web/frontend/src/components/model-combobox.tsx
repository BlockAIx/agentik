import { Button } from "@/components/ui/button"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { cn } from "@/lib/utils"
import { Check, ChevronsUpDown } from "lucide-react"
import { useCallback, useMemo, useState } from "react"

interface ModelComboboxProps {
  value: string
  onChange: (value: string) => void
  models: string[]
  loading?: boolean
  placeholder?: string
  className?: string
}

/** Max items shown in the dropdown before the user types a filter. */
const MAX_UNFILTERED = 50

export function ModelCombobox({
  value,
  onChange,
  models,
  loading = false,
  placeholder = "provider/model-name",
  className,
}: ModelComboboxProps): React.JSX.Element {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState("")

  // Filter models by search term.
  const filtered = useMemo(() => {
    if (!search) return models.slice(0, MAX_UNFILTERED)
    const lower = search.toLowerCase()
    return models.filter((m) => m.toLowerCase().includes(lower)).slice(0, 100)
  }, [models, search])

  // Group filtered models by provider.
  const groups = useMemo(() => {
    const map = new Map<string, string[]>()
    for (const m of filtered) {
      const slash = m.indexOf("/")
      const provider = slash > 0 ? m.slice(0, slash) : "other"
      const existing = map.get(provider)
      if (existing) {
        existing.push(m)
      } else {
        map.set(provider, [m])
      }
    }
    return map
  }, [filtered])

  const handleSelect = useCallback(
    (model: string) => {
      onChange(model)
      setOpen(false)
    },
    [onChange],
  )

  // Display text: show model short name if selected.
  const displayValue = value || placeholder

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className={cn(
            "justify-between font-mono text-xs h-8",
            !value && "text-muted-foreground",
            className,
          )}
        >
          <span className="truncate">{displayValue}</span>
          <ChevronsUpDown className="ml-1 h-3 w-3 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[400px] p-0" align="start">
        <Command shouldFilter={false}>
          <CommandInput
            placeholder="Search models..."
            value={search}
            onValueChange={setSearch}
          />
          <CommandList>
            <CommandEmpty>
              {loading
                ? "Loading models..."
                : search
                ? "No models found. You can still type a custom model ID."
                : "No models available. You can still type a custom model ID."}
            </CommandEmpty>
            {/* Allow using custom value that isn't in the catalog */}
            {search && !models.includes(search) && (
              <CommandGroup heading="Custom">
                <CommandItem
                  value={search}
                  onSelect={() => handleSelect(search)}
                  className="font-mono text-xs"
                >
                  <Check
                    className={cn(
                      "mr-2 h-3 w-3",
                      value === search ? "opacity-100" : "opacity-0",
                    )}
                  />
                  {search}
                </CommandItem>
              </CommandGroup>
            )}
            {[...groups.entries()].map(([provider, items]) => (
              <CommandGroup key={provider} heading={provider}>
                {items.map((model) => (
                  <CommandItem
                    key={model}
                    value={model}
                    onSelect={() => handleSelect(model)}
                    className="font-mono text-xs"
                  >
                    <Check
                      className={cn(
                        "mr-2 h-3 w-3",
                        value === model ? "opacity-100" : "opacity-0",
                      )}
                    />
                    {model.slice(model.indexOf("/") + 1)}
                  </CommandItem>
                ))}
              </CommandGroup>
            ))}
            {!search && models.length > MAX_UNFILTERED && (
              <div className="p-2 text-xs text-center text-muted-foreground">
                Type to search {models.length.toLocaleString()} models...
              </div>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
