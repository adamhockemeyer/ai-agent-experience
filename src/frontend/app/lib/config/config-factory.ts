import type { ConfigInterface } from "./config-interface"
import { AzureAppConfig } from "./azure-app-config"
import { MemoryConfig } from "./memory-config"
import type { WebsiteConfig } from "@/lib/types"

// Track if we're using default values
let isUsingDefaults = false

// Define the agent prefix to match the one in agent-actions.ts
const AGENT_PREFIX = "agent:"

/**
 * Factory for creating configuration providers
 */
export class ConfigFactory {
  /**
   * Create a configuration provider based on environment
   * @returns A ConfigInterface implementation
   */
  static createConfigProvider(): ConfigInterface {
    // First check if Azure App Configuration endpoint is configured (for DefaultAzureCredential)
    if (process.env.AZURE_APPCONFIG_ENDPOINT) {
      try {
        console.log(
          `Creating Azure App Config with endpoint: ${process.env.AZURE_APPCONFIG_ENDPOINT} and DefaultAzureCredential`,
        )
        const azureConfig = new AzureAppConfig()

        // Wrap with fallback to defaults
        return new ConfigProviderWithFallback(azureConfig)
      } catch (error) {
        console.error(
          "Failed to initialize Azure App Configuration with endpoint, falling back to connection string:",
          error,
        )
      }
    }

    // Then check if Azure App Configuration connection string is configured
    if (process.env.AZURE_APP_CONFIG_CONNECTION_STRING) {
      try {
        // Create Azure App Config without any labels
        console.log(`Creating Azure App Config with connection string`)

        const azureConfig = new AzureAppConfig(process.env.AZURE_APP_CONFIG_CONNECTION_STRING)

        // Wrap with fallback to defaults
        return new ConfigProviderWithFallback(azureConfig)
      } catch (error) {
        console.error(
          "Failed to initialize Azure App Configuration with connection string, falling back to memory config:",
          error,
        )
        isUsingDefaults = true

        // Create memory config with minimal default settings (no agents or model mappings)
        return new MemoryConfig({
          website: getDefaultWebsiteConfig(),
        })
      }
    }

    // Fall back to in-memory config with minimal default settings
    console.log(
      "No Azure App Configuration connection string or endpoint found, using memory config with minimal defaults",
    )
    isUsingDefaults = true
    return new MemoryConfig({
      website: getDefaultWebsiteConfig(),
    })
  }
}

// Create a default website config with empty collections for agents and model mappings
function getDefaultWebsiteConfig(): WebsiteConfig {
  return {
    name: "AI Agents Experience",
    authenticationEnabled: false,
    modelMappings: [],
    menuHiddenAgentIds: []
  }
}

/**
 * Wrapper for config provider that falls back to defaults when configuration is not found
 */
class ConfigProviderWithFallback implements ConfigInterface {
  private provider: ConfigInterface
  private fallbackProvider: MemoryConfig

  constructor(provider: ConfigInterface) {
    this.provider = provider

    // Initialize fallback provider with minimal default settings
    this.fallbackProvider = new MemoryConfig({
      website: getDefaultWebsiteConfig(),
    })
  }

  async getConfig<T>(key: string): Promise<T | null> {
    try {
      const value = await this.provider.getConfig<T>(key)

      // If value is found, we're not using defaults
      if (value !== null) {
        isUsingDefaults = false
        return value
      }

      // If value is not found, use fallback
      isUsingDefaults = true

      // For agents, don't return default mock data
      if (key.startsWith(AGENT_PREFIX)) {
        return null
      }

      return await this.fallbackProvider.getConfig<T>(key)
    } catch (error) {
      console.error(`Error in getConfig for key ${key}:`, error)

      // Fall back to defaults, but don't return mock agents
      isUsingDefaults = true

      if (key.startsWith(AGENT_PREFIX)) {
        return null
      }

      return await this.fallbackProvider.getConfig<T>(key)
    }
  }

  async getAllConfigs<T>(prefix?: string): Promise<Record<string, T>> {
    try {
      const configs = await this.provider.getAllConfigs<T>(prefix)

      // If configs are found, we're not using defaults
      if (Object.keys(configs).length > 0) {
        isUsingDefaults = false
        return configs
      }

      // If no configs found, use fallback
      isUsingDefaults = true

      // For agents, return empty object instead of mock data
      if (prefix === AGENT_PREFIX) {
        return {}
      }

      return await this.fallbackProvider.getAllConfigs<T>(prefix)
    } catch (error) {
      console.error(`Error in getAllConfigs with prefix ${prefix}:`, error)

      // Fall back to defaults, but return empty object for agents
      isUsingDefaults = true

      if (prefix === AGENT_PREFIX) {
        return {}
      }

      return await this.fallbackProvider.getAllConfigs<T>(prefix)
    }
  }

  async upsertConfig<T>(key: string, value: T, contentType?: string): Promise<boolean> {
    try {
      const success = await this.provider.upsertConfig(key, value, contentType)

      // If successfully saved to the real provider, we're no longer using defaults
      if (success) {
        isUsingDefaults = false

        // Also update the fallback provider to keep it in sync
        await this.fallbackProvider.upsertConfig(key, value, contentType)
        return true
      }

      // If failed to save to real provider, save to fallback
      isUsingDefaults = true
      return await this.fallbackProvider.upsertConfig(key, value, contentType)
    } catch (error) {
      console.error(`Error in upsertConfig for key ${key}:`, error)

      // Fall back to memory config
      isUsingDefaults = true
      return await this.fallbackProvider.upsertConfig(key, value, contentType)
    }
  }

  async deleteConfig(key: string): Promise<boolean> {
    try {
      const success = await this.provider.deleteConfig(key)

      // Also delete from fallback provider to keep it in sync
      if (success) {
        await this.fallbackProvider.deleteConfig(key)
      }

      return success
    } catch (error) {
      console.error(`Error in deleteConfig for key ${key}:`, error)

      // Fall back to memory config
      isUsingDefaults = true
      return await this.fallbackProvider.deleteConfig(key)
    }
  }
}

// Singleton instance of the config provider
let configProvider: ConfigInterface | null = null

/**
 * Get the configuration provider instance
 * @returns The ConfigInterface implementation
 */
export function getConfigProvider(): ConfigInterface {
  if (!configProvider) {
    configProvider = ConfigFactory.createConfigProvider()
  }
  return configProvider
}

/**
 * Check if the application is using default configuration values
 * @returns True if using defaults, false if using stored configuration
 */
export function isUsingDefaultConfig(): boolean {
  return isUsingDefaults
}

/**
 * Reset the isUsingDefaults flag to false
 * This is useful when we know we're not using defaults
 */
export function resetUsingDefaultConfig(): void {
  isUsingDefaults = false
}

// Export the agent prefix for use in other files
export { AGENT_PREFIX }
