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
import { Copy, Check, Download } from "lucide-react"
import { useToast } from "@/components/ui/use-toast"

interface ExportConfigDialogProps {
  isOpen: boolean
  onOpenChange: (open: boolean) => void
  exportedConfig: string
  agentId: string
}

export default function ExportConfigDialog({ isOpen, onOpenChange, exportedConfig, agentId }: ExportConfigDialogProps) {
  const [isCopied, setIsCopied] = useState(false)
  const { toast } = useToast()

  const handleCopyConfig = () => {
    navigator.clipboard.writeText(exportedConfig)
    setIsCopied(true)
    toast({
      title: "Copied",
      description: "Agent configuration has been copied to clipboard.",
    })

    // Reset copy state after 2 seconds
    setTimeout(() => {
      setIsCopied(false)
    }, 2000)
  }

  const handleDownloadConfig = () => {
    // Create a blob from the JSON data
    const blob = new Blob([exportedConfig], { type: "application/json" })
    const url = URL.createObjectURL(blob)

    // Create a temporary link and trigger download
    const link = document.createElement("a")
    link.href = url
    link.download = `${agentId}_config.json`
    document.body.appendChild(link)
    link.click()

    // Clean up
    document.body.removeChild(link)
    URL.revokeObjectURL(url)

    toast({
      title: "Downloaded",
      description: "Agent configuration has been downloaded.",
    })
  }

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>Agent Configuration</DialogTitle>
          <DialogDescription>
            This is the JSON configuration for your agent. You can copy it or download it as a file.
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-auto mt-4 mb-4">
          <pre className="bg-slate-50 dark:bg-slate-900 p-4 rounded-md border text-sm font-mono overflow-auto max-h-[50vh]">
            {exportedConfig}
          </pre>
        </div>

        <DialogFooter className="flex justify-between items-center">
          <div className="text-sm text-muted-foreground">{agentId}_config.json</div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={handleCopyConfig} className="gap-2">
              {isCopied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              {isCopied ? "Copied" : "Copy"}
            </Button>
            <Button onClick={handleDownloadConfig} className="gap-2">
              <Download className="h-4 w-4" />
              Download
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
