/** Card wrapper with an optional capped-height scrollable content area. */
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import type React from "react"

interface TileProps {
  title?: React.ReactNode
  action?: React.ReactNode
  /** CSS max-height for the scrollable area, e.g. "350px" or "50vh". */
  maxH?: string
  /** When true, both axes scroll. */
  scrollBoth?: boolean
  /** Remove CardContent padding (flush tables). */
  flush?: boolean
  className?: string
  children: React.ReactNode
}
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
            "flex flex-row items-center",
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
