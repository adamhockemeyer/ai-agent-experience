import type { ConfigInterface } from "./config-interface"

/**
 * In-memory implementation of the ConfigInterface for development and testing
 */
export class MemoryConfig implements ConfigInterface {
  private configs: Map<string, any>
  private contentTypes: Map<string, string>

  constructor(initialData: Record<string, any> = {}) {
    this.configs = new Map(Object.entries(initialData))
    this.contentTypes = new Map()
  }

  /**
   * Get a configuration value by key
   * @param key The configuration key
   * @returns The configuration value or null if not found
   */
  async getConfig<T>(key: string): Promise<T | null> {
    if (this.configs.has(key)) {
      return this.configs.get(key) as T
    }
    return null
  }

  /**
   * Get all configuration values with an optional prefix
   * @param prefix Optional prefix to filter configuration keys
   * @returns Object containing all matching configuration values
   */
  async getAllConfigs<T>(prefix?: string): Promise<Record<string, T>> {
    const result: Record<string, T> = {}

    for (const [key, value] of this.configs.entries()) {
      if (!prefix || key.startsWith(prefix)) {
        result[key] = value as T
      }
    }

    return result
  }

  /**
   * Create or update a configuration value
   * @param key The configuration key
   * @param value The configuration value
   * @param contentType Optional content type for the configuration value
   * @returns True if successful
   */
  async upsertConfig<T>(key: string, value: T, contentType?: string): Promise<boolean> {
    this.configs.set(key, value)
    if (contentType) {
      this.contentTypes.set(key, contentType)
    }
    return true
  }

  /**
   * Delete a configuration value
   * @param key The configuration key
   * @returns True if successful
   */
  async deleteConfig(key: string): Promise<boolean> {
    const result = this.configs.delete(key)
    this.contentTypes.delete(key)
    return result
  }
}
