/**
 * Interface for configuration operations
 * This provides a common interface for different configuration providers
 */
export interface ConfigInterface {
  /**
   * Get a configuration value by key
   * @param key The configuration key
   * @returns The configuration value or null if not found
   */
  getConfig<T>(key: string): Promise<T | null>

  /**
   * Get all configuration values with an optional prefix
   * @param prefix Optional prefix to filter configuration keys
   * @returns Object containing all matching configuration values
   */
  getAllConfigs<T>(prefix?: string): Promise<Record<string, T>>

  /**
   * Create or update a configuration value
   * @param key The configuration key
   * @param value The configuration value
   * @param contentType Optional content type for the configuration value
   * @returns True if successful
   */
  upsertConfig<T>(key: string, value: T, contentType?: string): Promise<boolean>

  /**
   * Delete a configuration value
   * @param key The configuration key
   * @returns True if successful
   */
  deleteConfig(key: string): Promise<boolean>
}
