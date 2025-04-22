"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Settings, Bot, PlusCircle, Workflow } from "lucide-react"
import { getAgents } from "@/app/actions/agent-actions"
import { cn } from "@/lib/utils"
import type { Agent } from "@/lib/types"
import { isUsingDefaultConfig } from "@/lib/config/config-factory"
import { getWebsiteConfig } from "@/app/actions/website-actions"

export default function Sidebar() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [isUsingDefaults, setIsUsingDefaults] = useState(false)
  const [hiddenAgentIds, setHiddenAgentIds] = useState<string[]>([])
  const pathname = usePathname()

  useEffect(() => {
    const loadAgents = async () => {
      try {
        const [agentData, websiteConfig] = await Promise.all([getAgents(), getWebsiteConfig()])
        setAgents(agentData)
        setHiddenAgentIds(websiteConfig.menuHiddenAgentIds || [])
        setIsUsingDefaults(isUsingDefaultConfig())
      } catch (error) {
        console.error("Failed to load agents:", error)
      } finally {
        setLoading(false)
      }
    }

    loadAgents()
  }, [])

  return (
    <div className="w-64 border-r bg-background h-full flex flex-col">
      <div className="p-4">
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider px-2">Available Agents</h2>
      </div>
      <Separator />
      <ScrollArea className="flex-1">
        <div className="p-4 space-y-1">
          {loading ? (
            <div className="text-sm text-muted-foreground">Loading agents...</div>
          ) : agents.length === 0 ? (
            <div className="text-sm text-muted-foreground px-2">
              {isUsingDefaults ? (
                <div className="space-y-4 pt-4">
                  <p>You need to configure your first agent.</p>
                  <Link href="/settings?tab=models">
                    <Button variant="outline" size="sm" className="w-full justify-start">
                      <PlusCircle className="mr-2 h-4 w-4" />
                      Setup Models & Agents
                    </Button>
                  </Link>
                </div>
              ) : (
                "No agents found. Create one in Settings."
              )}
            </div>
          ) : (
            agents
              .filter((agent) => !hiddenAgentIds?.includes(agent.id))
              .map((agent) => (
                <Link key={agent.id} href={`/agents/${agent.id}`}>
                  <div
                    className={cn(
                      "flex items-center px-3 py-2 rounded-md text-sm",
                      pathname === `/agents/${agent.id}`
                        ? "bg-primary/10 text-primary font-medium"
                        : "hover:bg-primary/5 hover:text-primary",
                    )}
                  >
                    {agent.tools && agent.tools.some((tool) => tool.type === "Agent") ? (
                      <Workflow className="mr-2 h-4 w-4" />
                    ) : (
                      <Bot className="mr-2 h-4 w-4" />
                    )}
                    <span className="truncate">{agent.name}</span>
                  </div>
                </Link>
              ))
          )}
        </div>
      </ScrollArea>
      <div className="p-4 border-t">
        <Link href="/settings">
          <Button variant="ghost" className="w-full justify-start">
            <Settings className="mr-2 h-4 w-4" />
            Settings
          </Button>
        </Link>
      </div>
    </div>
  )
}
