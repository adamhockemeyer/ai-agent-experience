"use client"

import { useState, useEffect } from "react"
import type { WebsiteConfig } from "@/lib/types"
import { getWebsiteConfig } from "@/app/actions/config-actions"
import { useToast } from "@/components/ui/use-toast"

/**
 * Custom hook to fetch website configuration
 */
export function useWebsiteConfig() {
  const [websiteConfig, setWebsiteConfig] = useState<WebsiteConfig | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const { toast } = useToast()

  useEffect(() => {
    const fetchWebsiteConfig = async () => {
      setIsLoading(true)
      try {
        const config = await getWebsiteConfig()
        setWebsiteConfig(config)
      } catch (error) {
        console.error("Error fetching website config:", error)
        toast({
          title: "Error",
          description: "Failed to load website configuration.",
          variant: "destructive",
        })
      } finally {
        setIsLoading(false)
      }
    }

    fetchWebsiteConfig()
  }, [toast])

  return { websiteConfig, isLoading }
}
