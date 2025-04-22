"use client"

import { useState, useEffect } from "react"
import type { Agent } from "@/lib/types"
import { getAgents } from "@/app/actions/agent-actions"
import { useToast } from "@/components/ui/use-toast"

/**
 * Custom hook to fetch available agents
 */
export function useAvailableAgents(isEditing: boolean, currentAgentId?: string) {
  const [agents, setAgents] = useState<Agent[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const { toast } = useToast()

  useEffect(() => {
    const fetchAgents = async () => {
      setIsLoading(true)
      try {
        const agentData = await getAgents()
        // Filter out the current agent if we're editing
        const filteredAgents =
          isEditing && currentAgentId ? agentData.filter((a) => a.id !== currentAgentId) : agentData
        setAgents(filteredAgents)
      } catch (error) {
        console.error("Error fetching agents:", error)
        toast({
          title: "Error",
          description: "Failed to load available agents.",
          variant: "destructive",
        })
      } finally {
        setIsLoading(false)
      }
    }

    fetchAgents()
  }, [isEditing, currentAgentId, toast])

  return { agents, isLoading }
}
