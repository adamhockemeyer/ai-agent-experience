"use server"

import type { WebsiteConfig } from "@/lib/types"
import { getConfigProvider } from "@/lib/config/config-factory"

const configProvider = getConfigProvider()

// Update the getWebsiteConfig function to accept a cache-busting parameter
export async function getWebsiteConfig(cacheBuster?: string): Promise<WebsiteConfig> {
  try {
    // Get website config from the config provider
    // We ignore the cacheBuster parameter here since it's just used for the function signature
    // to allow components to force a fresh fetch
    const config = await configProvider.getConfig<WebsiteConfig>("website")

    if (!config) {
      console.log("Website configuration not found, using default config")
      // Return minimal default config
      return {
        name: "AI Agents Showcase",
        authenticationEnabled: false,
        modelMappings: [], // Empty by default
        menuHiddenAgentIds: [],
      }
    }

    return config
  } catch (error) {
    console.error("Error getting website config:", error)
    // Return minimal default config
    return {
      name: "AI Agents Showcase",
      authenticationEnabled: false,
      modelMappings: [], // Empty by default
      menuHiddenAgentIds: [],
    }
  }
}
