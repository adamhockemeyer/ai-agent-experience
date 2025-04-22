"use client"

import type React from "react"

import { Button } from "@/components/ui/button"
import { Download } from "lucide-react"
import { useToast } from "@/components/ui/use-toast"

interface AgentVisualizationActionsProps {
  svgRef: React.RefObject<SVGSVGElement>
}

export default function AgentVisualizationActions({ svgRef }: AgentVisualizationActionsProps) {
  const { toast } = useToast()

  const downloadSvgAsImage = () => {
    if (!svgRef.current) return

    const svg = svgRef.current

    try {
      // Get the SVG data as a string
      const serializer = new XMLSerializer()
      let source = serializer.serializeToString(svg)

      // Add namespaces if they're missing
      if (!source.match(/^<svg[^>]+xmlns="http:\/\/www\.w3\.org\/2000\/svg"/)) {
        source = source.replace(/^<svg/, '<svg xmlns="http://www.w3.org/2000/svg"')
      }

      // Add CSS styles inline
      const style = document.createElement("style")
      style.textContent = `
        text { font-family: ui-sans-serif, system-ui, sans-serif; }
        .font-medium { font-weight: 500; }
      `

      // Create a new SVG with styles
      const svgWithStyles = svg.cloneNode(true) as SVGSVGElement
      svgWithStyles.insertBefore(style, svgWithStyles.firstChild)
      source = serializer.serializeToString(svgWithStyles)

      // Convert SVG to data URL directly
      const svgBlob = new Blob([source], { type: "image/svg+xml;charset=utf-8" })
      const url = URL.createObjectURL(svgBlob)

      // Create a download link for the SVG directly
      const a = document.createElement("a")
      a.href = url
      a.download = "agent-visualization.svg"
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)

      toast({
        title: "SVG Downloaded",
        description: "Agent visualization has been downloaded as an SVG file.",
      })
    } catch (error) {
      console.error("Error downloading SVG:", error)
      toast({
        title: "Download Failed",
        description: "Failed to download the visualization. Please try again.",
        variant: "destructive",
      })
    }
  }

  return (
    <Button variant="outline" size="xs" onClick={downloadSvgAsImage} className="h-7 px-2 text-xs">
      <Download className="h-3 w-3 mr-1" />
      Download
    </Button>
  )
}
