"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import yaml from "js-yaml"

interface SpecViewDialogProps {
  isOpen: boolean
  onOpenChange: (open: boolean) => void
  specData: any
  specUrl: string
  specTitle?: string
  initialFormat?: "json" | "yaml"
}

export default function SpecViewDialog({
  isOpen,
  onOpenChange,
  specData,
  specUrl,
  specTitle,
  initialFormat = "json",
}: SpecViewDialogProps) {
  const [format, setFormat] = useState<"json" | "yaml">(initialFormat)

  // Function to format OpenAPI spec for display
  const formatSpecForDisplay = (spec: any, format: "json" | "yaml" = "json") => {
    if (!spec) return "No specification data available"

    try {
      if (format === "json") {
        return JSON.stringify(spec, null, 2)
      } else if (format === "yaml") {
        return yaml.dump(spec)
      }
    } catch (error) {
      console.error(`Error formatting spec as ${format}:`, error)
      return `Error formatting as ${format}: ${error instanceof Error ? error.message : String(error)}`
    }

    return "No specification data available"
  }

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>{specTitle || "OpenAPI Specification"}</DialogTitle>
          <DialogDescription>Full OpenAPI specification from {specUrl}</DialogDescription>
        </DialogHeader>

        <div className="flex justify-end gap-2 mb-2">
          <div className="bg-secondary rounded-md p-1 flex">
            <Button
              variant={format === "json" ? "default" : "ghost"}
              size="sm"
              onClick={() => setFormat("json")}
              className="rounded-r-none"
            >
              JSON
            </Button>
            <Button
              variant={format === "yaml" ? "default" : "ghost"}
              size="sm"
              onClick={() => setFormat("yaml")}
              className="rounded-l-none"
            >
              YAML
            </Button>
          </div>
        </div>

        <div className="flex-1 overflow-auto mt-2 mb-4">
          <pre className="bg-slate-50 dark:bg-slate-900 p-4 rounded-md border text-sm font-mono overflow-auto max-h-[50vh]">
            {formatSpecForDisplay(specData, format)}
          </pre>
        </div>

        <DialogFooter>
          <Button onClick={() => onOpenChange(false)}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
