"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Bot } from "lucide-react"
import type { WebsiteConfig } from "@/lib/types"
import { getWebsiteConfig } from "@/app/actions/config-actions"

export default function Header() {
  const [websiteConfig, setWebsiteConfig] = useState<WebsiteConfig | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const loadConfig = async () => {
      try {
        setIsLoading(true)
        // Add a timestamp to force a fresh fetch
        const config = await getWebsiteConfig(`_t=${Date.now()}`)
        setWebsiteConfig(config)
        setError(null)
      } catch (error) {
        console.error("Failed to load website config:", error)
        setError("Failed to load configuration. Check Azure App Configuration labels.")
        // Use default name if config fails to load
        setWebsiteConfig({
          name: "AI Agents Showcase",
          authenticationEnabled: false,
          modelMappings: [],
          menuHiddenAgentIds: [],
        })
      } finally {
        setIsLoading(false)
      }
    }

    loadConfig()

    // Set up an event listener for config changes
    const handleConfigChange = () => {
      loadConfig()
    }

    window.addEventListener("website-config-updated", handleConfigChange)

    return () => {
      window.removeEventListener("website-config-updated", handleConfigChange)
    }
  }, [])

  // Default name to use if config is still loading or failed to load
  const siteName = websiteConfig?.name || "AI Agents Showcase"
  const authEnabled = websiteConfig?.authenticationEnabled || false

  return (
    <header className="w-full border-b bg-background">
      <div className="flex h-16 items-center px-4 justify-between w-full">
        <Link href="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
          <Bot className="h-6 w-6 text-primary" />
          <h1 className="text-xl font-semibold">{isLoading ? "Loading..." : siteName}</h1>
        </Link>
        <div className="flex items-center gap-4">{authEnabled && <Button variant="outline">Sign In</Button>}</div>
      </div>
    </header>
  )
}
