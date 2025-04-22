"use client"

import { useRef, memo } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Bot, FileText, Code, FileJson } from "lucide-react"
import type { Tool } from "@/lib/types"
import AgentVisualizationActions from "./agent-visualization-actions"

interface AgentVisualizationProps {
  agentName: string
  agentType?: "AzureAIAgent" | "ChatCompletionAgent"
  tools: Tool[]
  codeInterpreter: boolean
  fileUpload: boolean
  displayFunctionCallStatus?: boolean
}

// Use memo to prevent unnecessary re-renders
const AgentVisualization = memo(function AgentVisualization({
  agentName,
  agentType = "ChatCompletionAgent",
  tools,
  codeInterpreter,
  fileUpload,
  displayFunctionCallStatus = false,
}: AgentVisualizationProps) {
  const svgRef = useRef<SVGSVGElement>(null)

  // Use completely fixed dimensions to avoid any resize observation
  const width = 300
  const height = 200 + Math.max(0, (tools.length + (codeInterpreter ? 1 : 0) + (fileUpload ? 1 : 0) - 3) * 30)

  // Calculate total nodes once to avoid recalculations
  const totalNodes = tools.length + (codeInterpreter ? 1 : 0) + (fileUpload ? 1 : 0)

  // Position calculations
  const agentX = width / 3
  const agentY = height / 2
  const startY = Math.max(40, (height - totalNodes * 40) / 2 + 20)

  // Create node positions array once
  const nodePositions = Array.from({ length: totalNodes }).map((_, i) => ({
    x: width - 80,
    y: startY + i * 40,
  }))

  return (
    <Card className="mt-2">
      <CardContent className="p-3">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-medium">Agent Visualization</h3>
          <AgentVisualizationActions svgRef={svgRef} />
        </div>
        <div className="relative w-full">
          <svg
            ref={svgRef}
            width={width}
            height={height}
            viewBox={`0 0 ${width} ${height}`}
            className="w-full"
            style={{ minHeight: "180px" }}
          >
            {/* Draw lines from agent to tools */}
            {nodePositions.map((pos, i) => (
              <line
                key={`line-${i}`}
                x1={agentX + 20}
                y1={agentY}
                x2={pos.x - 20}
                y2={pos.y}
                stroke="#e2e8f0"
                strokeWidth="2"
                strokeDasharray="4"
              />
            ))}

            {/* Draw agent node - smaller */}
            <g transform={`translate(${agentX - 20}, ${agentY - 20})`}>
              <circle cx="20" cy="20" r="20" fill="#3b82f6" fillOpacity="0.2" />
              <circle cx="20" cy="20" r="16" fill="#3b82f6" />
              <foreignObject x="8" y="8" width="24" height="24">
                <div className="flex items-center justify-center h-full text-white">
                  <Bot className="h-4 w-4" />
                </div>
              </foreignObject>
            </g>

            {/* Agent name - smaller font */}
            <text x={agentX} y={agentY + 35} textAnchor="middle" fontSize="12" fontWeight="bold" fill="currentColor">
              {agentName || "Agent"}
            </text>

            {/* Draw tool nodes - smaller */}
            {tools.map((tool, i) => {
              const pos = nodePositions[i]
              return (
                <g key={`tool-${i}`} transform={`translate(${pos.x - 16}, ${pos.y - 16})`}>
                  <circle cx="16" cy="16" r="16" fill="#f97316" fillOpacity="0.2" />
                  <circle cx="16" cy="16" r="12" fill="#f97316" />
                  <foreignObject x="6" y="6" width="20" height="20">
                    <div className="flex items-center justify-center h-full text-white">
                      {tool.type === "OpenAPI" ? (
                        <FileJson className="h-3 w-3" />
                      ) : tool.type === "ModelContextProtocol" ? (
                        <div className="text-xs font-bold">MCP</div>
                      ) : (
                        <Bot className="h-3 w-3" />
                      )}
                    </div>
                  </foreignObject>
                  <text x="16" y="38" textAnchor="middle" fontSize="10" fill="currentColor" className="font-medium">
                    {tool.name}
                  </text>
                </g>
              )
            })}

            {/* Draw code interpreter node if enabled - smaller */}
            {codeInterpreter &&
              (() => {
                const pos = nodePositions[tools.length]
                return (
                  <g transform={`translate(${pos.x - 16}, ${pos.y - 16})`}>
                    <circle cx="16" cy="16" r="16" fill="#8b5cf6" fillOpacity="0.2" />
                    <circle cx="16" cy="16" r="12" fill="#8b5cf6" />
                    <foreignObject x="6" y="6" width="20" height="20">
                      <div className="flex items-center justify-center h-full text-white">
                        <Code className="h-3 w-3" />
                      </div>
                    </foreignObject>
                    <text x="16" y="38" textAnchor="middle" fontSize="10" fill="currentColor" className="font-medium">
                      Code
                    </text>
                  </g>
                )
              })()}

            {/* Draw file upload node if enabled - smaller */}
            {fileUpload &&
              (() => {
                const pos = nodePositions[tools.length + (codeInterpreter ? 1 : 0)]
                return (
                  <g transform={`translate(${pos.x - 16}, ${pos.y - 16})`}>
                    <circle cx="16" cy="16" r="16" fill="#10b981" fillOpacity="0.2" />
                    <circle cx="16" cy="16" r="12" fill="#10b981" />
                    <foreignObject x="6" y="6" width="20" height="20">
                      <div className="flex items-center justify-center h-full text-white">
                        <FileText className="h-3 w-3" />
                      </div>
                    </foreignObject>
                    <text x="16" y="38" textAnchor="middle" fontSize="10" fill="currentColor" className="font-medium">
                      Files
                    </text>
                  </g>
                )
              })()}
          </svg>
        </div>
      </CardContent>
    </Card>
  )
})

export default AgentVisualization
