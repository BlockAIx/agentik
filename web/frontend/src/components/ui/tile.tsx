/**
 * Tile — a card-like container with a reliably scrollable content area.
 *
 * Motivation: Radix ScrollArea's viewport uses `height: 100%`, which does NOT
 * resolve against a parent's `max-height` alone — it falls back to `auto`, so
 * content clips rather than scrolls. Tile uses a plain div with
 * `overflow-y-auto` + an inline `maxHeight` style, which always works in every
 * browser regardless of the containing-block height.
 */
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import type React from "react"

interface TileProps {
  /** Card title. Pass a string or a pre-built node (e.g. with an icon). */
  title?: React.ReactNode
  /** Optional element rendered on the trailing edge of the header (buttons, badges…). */
  action?: React.ReactNode
  /**
   * CSS max-height value for the scrollable content area.
   * Use CSS units: "350px", "50vh", "24rem", etc.
   * When omitted the content area grows naturally.
   */
  maxH?: string
  /**
   * When true both axes scroll (useful for code/diff blocks with wide lines).
   * When false (default) only vertical scroll is enabled; horizontal content
   * wraps or is hidden.
   */
  scrollBoth?: boolean
  /** Set to true to remove CardContent padding (flush tables, etc.). */
  flush?: boolean
  /** Extra classes forwarded to the Card root. */
  className?: string
  children: React.ReactNode
}

/**
 * Tile — Card wrapper with optional scrollable content area.
 * Use `maxH` to cap the height and enable vertical (or bidirectional) scrolling.
 */
export function Tile({
  title,
  action,
  maxH,
  scrollBoth = false,
  flush = false,
  className,
  children,
}: TileProps): React.JSX.Element {
  const hasHeader = title != null || action != null

  const content = maxH ? (
    <div
      className={cn(
        "w-full overflow-y-auto",
        scrollBoth ? "overflow-x-auto" : "overflow-x-hidden",
      )}
      style={{ maxHeight: maxH }}
    >
      {children}
    </div>
  ) : (
    children
  )

  return (
    <Card className={className}>
      {hasHeader && (
        <CardHeader
          className={cn(
            "flex flex-row items-center py-3",
            action ? "justify-between" : "",
          )}
        >
          {title != null && (
            <CardTitle className="text-sm flex items-center gap-1.5">{title}</CardTitle>
          )}
          {action}
        </CardHeader>
      )}
      <CardContent className={flush ? "py-0" : undefined}>{content}</CardContent>
    </Card>
  )
}
