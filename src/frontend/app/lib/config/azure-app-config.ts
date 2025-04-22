import { AppConfigurationClient } from "@azure/app-configuration"
import { DefaultAzureCredential } from "@azure/identity"
import type { ConfigInterface } from "./config-interface"
import { AGENT_PREFIX } from "./config-factory"

/**
 * Azure App Configuration implementation of the ConfigInterface
 */
export class AzureAppConfig implements ConfigInterface {
  private client: AppConfigurationClient
  private readonly defaultLabel?: string
  private readonly agentLabel?: string

  /**
   * Create a new AzureAppConfig instance
   * @param connectionString Azure App Configuration connection string (optional if endpoint is provided)
   * @param defaultLabel Optional default label for all configuration items
   * @param agentLabel Optional additional label for agent configuration items
   */
  constructor(connectionString?: string, defaultLabel?: string, agentLabel?: string) {
    try {
      // First try to use the endpoint with DefaultAzureCredential if available
      const endpoint = process.env.AZURE_APPCONFIG_ENDPOINT

      if (endpoint) {
        console.log(`Initializing Azure App Configuration with endpoint: ${endpoint} and DefaultAzureCredential`)
        const credential = new DefaultAzureCredential()
        this.client = new AppConfigurationClient(endpoint, credential)
      } else if (connectionString) {
        // Fall back to connection string if endpoint is not available
        console.log(`Initializing Azure App Configuration with connection string`)
        this.client = new AppConfigurationClient(connectionString)
      } else {
        throw new Error("Either AZURE_APPCONFIG_ENDPOINT or connection string must be provided")
      }

      this.defaultLabel = defaultLabel
      this.agentLabel = agentLabel
      console.log(
        `AzureAppConfig initialized with default label: ${defaultLabel || "none"}, agent label: ${agentLabel || "none"}`,
      )
    } catch (error) {
      console.error("Error initializing Azure App Configuration client:", error)
      throw new Error("Failed to initialize Azure App Configuration client")
    }
  }

  /**
   * Determine which label to use based on the key
   * @param key The configuration key
   * @returns The appropriate label or undefined if no labels are configured
   */
  private getLabel(key: string): string | undefined {
    // Use agent label for agent-related configurations if specified
    if (key.startsWith(AGENT_PREFIX) && this.agentLabel) {
      return this.agentLabel
    }
    // Use default label for all other configurations if specified
    return this.defaultLabel
  }

  /**
   * Get a configuration value by key
   * @param key The configuration key
   * @returns The configuration value or null if not found
   */
  async getConfig<T>(key: string): Promise<T | null> {
    try {
      // Check if client is initialized
      if (!this.client) {
        console.error("Azure App Configuration client is not initialized")
        return null
      }

      const label = this.getLabel(key)
      console.log(`Fetching config for key: ${key} with label: ${label || "none"}`)

      // Create settings options, only include label if it's defined
      const settingsOptions: any = { key }
      if (label !== undefined) {
        settingsOptions.label = label
      }

      const setting = await this.client.getConfigurationSetting(settingsOptions)

      if (setting.value) {
        try {
          console.log(`Found config for key: ${key}, content type: ${setting.contentType || "none"}`)
          return JSON.parse(setting.value) as T
        } catch {
          // If not valid JSON, return as is
          return setting.value as unknown as T
        }
      }
      console.log(`No config found for key: ${key} with label: ${label || "none"}`)
      return null
    } catch (error) {
      // Check for "not found" error which is expected for new configurations
      if (error && typeof error === "object" && "statusCode" in error && error.statusCode === 404) {
        console.log(`Config key ${key} with label ${this.getLabel(key) || "none"} not found in Azure App Configuration`)
        return null
      }

      console.error(`Error getting config for key ${key}:`, error)
      return null
    }
  }

  /**
   * Get all configuration values with an optional prefix
   * @param prefix Optional prefix to filter configuration keys
   * @returns Object containing all matching configuration values
   */
  async getAllConfigs<T>(prefix?: string): Promise<Record<string, T>> {
    try {
      // Check if client is initialized
      if (!this.client) {
        console.error("Azure App Configuration client is not initialized")
        return {}
      }

      // Determine which label to use based on the prefix
      const label = prefix?.startsWith(AGENT_PREFIX) && this.agentLabel ? this.agentLabel : this.defaultLabel
      console.log(`Fetching all configs with prefix: ${prefix || "none"} and label: ${label || "none"}`)

      // Create list options, only include label if it's defined
      const listOptions: any = {}
      if (prefix) {
        listOptions.keyFilter = `${prefix}*`
      }
      if (label !== undefined) {
        listOptions.labelFilter = label
      }

      const settings = this.client.listConfigurationSettings(listOptions)

      const configs: Record<string, T> = {}
      for await (const setting of settings) {
        if (setting.key && setting.value) {
          try {
            configs[setting.key] = JSON.parse(setting.value) as T
          } catch {
            configs[setting.key] = setting.value as unknown as T
          }
        }
      }

      console.log(`Found ${Object.keys(configs).length} configs with prefix: ${prefix || "none"}`)
      return configs
    } catch (error) {
      console.error(`Error getting all configs with prefix ${prefix}:`, error)
      return {}
    }
  }

  /**
   * Create or update a configuration value
   * @param key The configuration key
   * @param value The configuration value
   * @param contentType Optional content type for the configuration value
   * @returns True if successful
   */
  async upsertConfig<T>(key: string, value: T, contentType?: string): Promise<boolean> {
    try {
      // Check if client is initialized
      if (!this.client) {
        console.error("Azure App Configuration client is not initialized")
        return false
      }

      const label = this.getLabel(key)
      const stringValue = typeof value === "string" ? value : JSON.stringify(value)

      // Default to application/json for objects
      const finalContentType = contentType || (typeof value === "object" ? "application/json" : undefined)

      console.log(
        `Upserting config for key: ${key} with label: ${label || "none"}, content type: ${finalContentType || "none"}`,
      )

      // Create settings options, only include label if it's defined
      const settingsOptions: any = {
        key,
        value: stringValue,
      }

      if (label !== undefined) {
        settingsOptions.label = label
      }

      if (finalContentType !== undefined) {
        settingsOptions.contentType = finalContentType
      }

      await this.client.setConfigurationSetting(settingsOptions)

      console.log(`Successfully upserted config for key: ${key}`)
      return true
    } catch (error) {
      console.error(`Error upserting config for key ${key}:`, error)
      return false
    }
  }

  /**
   * Delete a configuration value
   * @param key The configuration key
   * @returns True if successful
   */
  async deleteConfig(key: string): Promise<boolean> {
    try {
      // Check if client is initialized
      if (!this.client) {
        console.error("Azure App Configuration client is not initialized")
        return false
      }

      const label = this.getLabel(key)
      console.log(`Deleting config for key: ${key} with label: ${label || "none"}`)

      // Create delete options, only include label if it's defined
      const deleteOptions: any = { key }
      if (label !== undefined) {
        deleteOptions.label = label
      }

      await this.client.deleteConfigurationSetting(deleteOptions)
      console.log(`Successfully deleted config for key: ${key}`)
      return true
    } catch (error) {
      console.error(`Error deleting config for key ${key}:`, error)
      return false
    }
  }
}
