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
import type { AvailableModel } from "@/lib/api"
import { cn } from "@/lib/utils"
import { Check, ChevronsUpDown } from "lucide-react"
import { useCallback, useMemo, useState } from "react"

interface ModelComboboxProps {
  value: string
  onChange: (value: string) => void
  models: AvailableModel[]
  loading?: boolean
  placeholder?: string
  className?: string
  /** When true, applies a red border to indicate the current value is not a known model. */
  invalid?: boolean
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
  invalid = false,
}: ModelComboboxProps): React.JSX.Element {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState("")

  // Filter models by search term.
  const filtered = useMemo(() => {
    if (!search) return models.slice(0, MAX_UNFILTERED)
    const lower = search.toLowerCase()
    return models.filter((m) => m.full_id.toLowerCase().includes(lower)).slice(0, 100)
  }, [models, search])

  // Group filtered models by provider.
  const groups = useMemo(() => {
    const map = new Map<string, AvailableModel[]>()
    for (const m of filtered) {
      const existing = map.get(m.provider)
      if (existing) {
        existing.push(m)
      } else {
        map.set(m.provider, [m])
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

  const displayValue = value || placeholder
  const customNotInList = search && !models.some((m) => m.full_id === search)

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
            invalid && "border-destructive text-destructive focus:ring-destructive",
            className,
          )}
        >
          <span className="truncate">{displayValue}</span>
          <ChevronsUpDown className="ml-1 h-3 w-3 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-120 p-0" align="start">
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
            {customNotInList && (
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
                {items.map((m) => {
                  return (
                    <CommandItem
                      key={m.full_id}
                      value={m.full_id}
                      onSelect={() => handleSelect(m.full_id)}
                      className="font-mono text-xs"
                    >
                      <Check
                        className={cn(
                          "mr-2 h-3 w-3 shrink-0",
                          value === m.full_id ? "opacity-100" : "opacity-0",
                        )}
                      />
                      <span className="flex-1 truncate">{m.model}</span>
                    </CommandItem>
                  )
                })}
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
