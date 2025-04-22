"use server"

import type { WebsiteConfig, ModelMapping } from "@/lib/types"
import { v4 as uuidv4 } from "uuid"
import {
  getConfigProvider,
  isUsingDefaultConfig,
  resetUsingDefaultConfig as _resetUsingDefaultConfig,
} from "@/lib/config/config-factory"

const configProvider = getConfigProvider()

// Fix the getWebsiteConfig function to use the correct key
export async function getWebsiteConfig(): Promise<WebsiteConfig & { isUsingDefaults?: boolean }> {
  try {
    // Get website config from the config provider - use the correct key "website"
    const config = await configProvider.getConfig<WebsiteConfig>("website")

    if (!config) {
      console.log("Website configuration not found, using default config")
      // Return minimal default config with isUsingDefaults flag
      return {
        name: "AI Agents Showcase",
        authenticationEnabled: false,
        modelMappings: [], // Empty by default
        menuHiddenAgentIds: [], // Initialize with empty array
        isUsingDefaults: true,
      }
    }

    // If we have model mappings, we're definitely not using defaults
    if (config.modelMappings && config.modelMappings.length > 0) {
      _resetUsingDefaultConfig()
    }

    // Ensure menuHiddenAgentIds is always initialized
    const configWithDefaults = {
      ...config,
      menuHiddenAgentIds: config.menuHiddenAgentIds || [],
    }

    // Add flag indicating if we're using default values
    return {
      ...configWithDefaults,
      isUsingDefaults: isUsingDefaultConfig(),
    }
  } catch (error) {
    console.error("Error getting website config:", error)
    // Return minimal default config with isUsingDefaults flag
    return {
      name: "AI Agents Showcase",
      authenticationEnabled: false,
      modelMappings: [], // Empty by default
      menuHiddenAgentIds: [], // Initialize with empty array
      isUsingDefaults: true,
    }
  }
}

// Update the updateWebsiteConfig function to ensure it returns the latest data
export async function updateWebsiteConfig(config: Partial<WebsiteConfig>): Promise<WebsiteConfig> {
  try {
    // Get current config
    const currentConfig = await getWebsiteConfig()

    // Remove the isUsingDefaults flag before saving
    const { isUsingDefaults, ...configWithoutFlag } = currentConfig

    // Ensure menuHiddenAgentIds is initialized if missing
    const baseConfig = {
      ...configWithoutFlag,
      menuHiddenAgentIds: configWithoutFlag.menuHiddenAgentIds || [],
    }

    // Merge with updates
    const updatedConfig = { ...baseConfig, ...config }

    console.log("Saving config:", updatedConfig)

    // Save to config provider with application/json content type
    const success = await configProvider.upsertConfig("website", updatedConfig, "application/json")

    if (!success) {
      throw new Error("Failed to update website configuration")
    }

    // After successful save, we're definitely not using defaults
    _resetUsingDefaultConfig()

    // Dispatch an event to notify components that the config has been updated
    if (typeof window !== "undefined") {
      window.dispatchEvent(new Event("website-config-updated"))
    }

    // Return the updated config
    return updatedConfig
  } catch (error) {
    console.error("Error updating website config:", error)
    throw error
  }
}

export async function addModelMapping(mapping: Omit<ModelMapping, "id">): Promise<ModelMapping> {
  const newMapping: ModelMapping = {
    ...mapping,
    id: `model_${uuidv4().substring(0, 8)}`,
  }

  // Get current config
  const currentConfig = await getWebsiteConfig()

  // Add new mapping
  const updatedConfig = {
    ...currentConfig,
    modelMappings: [...currentConfig.modelMappings, newMapping],
  }

  // Save to config provider with application/json content type
  const success = await configProvider.upsertConfig("website", updatedConfig, "application/json")

  if (!success) {
    throw new Error("Failed to add model mapping")
  }

  return newMapping
}

export async function updateModelMapping(id: string, mapping: Partial<ModelMapping>): Promise<ModelMapping> {
  // Get current config
  const currentConfig = await getWebsiteConfig()

  // Find the mapping to update
  const index = currentConfig.modelMappings.findIndex((m) => m.id === id)
  if (index === -1) {
    throw new Error(`Model mapping with id ${id} not found`)
  }

  // Update the mapping
  const updatedMapping = { ...currentConfig.modelMappings[index], ...mapping }
  const updatedMappings = [...currentConfig.modelMappings]
  updatedMappings[index] = updatedMapping

  // Save to config provider with application/json content type
  const updatedConfig = {
    ...currentConfig,
    modelMappings: updatedMappings,
  }

  const success = await configProvider.upsertConfig("website", updatedConfig, "application/json")

  if (!success) {
    throw new Error("Failed to update model mapping")
  }

  return updatedMapping
}

export async function deleteModelMapping(id: string): Promise<void> {
  // Get current config
  const currentConfig = await getWebsiteConfig()

  // Filter out the mapping to delete
  const updatedMappings = currentConfig.modelMappings.filter((m) => m.id !== id)

  // If no change, the mapping wasn't found
  if (updatedMappings.length === currentConfig.modelMappings.length) {
    throw new Error(`Model mapping with id ${id} not found`)
  }

  // Save to config provider with application/json content type
  const updatedConfig = {
    ...currentConfig,
    modelMappings: updatedMappings,
  }

  const success = await configProvider.upsertConfig("website", updatedConfig, "application/json")

  if (!success) {
    throw new Error("Failed to delete model mapping")
  }
}

export const resetUsingDefaultConfig = _resetUsingDefaultConfig
