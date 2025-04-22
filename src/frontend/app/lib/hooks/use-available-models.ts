"use client"

import { useState, useEffect, useRef } from "react"
import type { WebsiteConfig, ModelMapping } from "@/lib/types"
import { useToast } from "@/components/ui/use-toast"

/**
 * Custom hook to manage available models based on agent type and provider
 */
export function useAvailableModels(
  websiteConfig: WebsiteConfig | null,
  agentType: string,
  provider: string,
  setFormValue: (field: string, value: any) => void,
) {
  const [availableModels, setAvailableModels] = useState<ModelMapping[]>([])
  const { toast } = useToast()

  // Use refs to track if we've already updated these values to prevent infinite loops
  const hasUpdatedProvider = useRef(false)
  const hasUpdatedModel = useRef(false)

  useEffect(() => {
    // Reset our update tracking when dependencies change
    hasUpdatedProvider.current = false
    hasUpdatedModel.current = false

    if (!websiteConfig) return

    // First, find all available providers for the selected agent type
    const availableProviders = websiteConfig.modelMappings
      .filter((model) => model.enabled && model.agentType === agentType)
      .map((model) => model.provider)

    const uniqueProviders = [...new Set(availableProviders)]

    // Check if current provider has models for this agent type
    const currentProviderHasModels = availableProviders.includes(provider)

    // If current provider doesn't have models but other providers do, switch to the first available provider
    let providerToUse = provider
    if (!currentProviderHasModels && uniqueProviders.length > 0 && !hasUpdatedProvider.current) {
      providerToUse = uniqueProviders[0]
      // Update the provider in the form
      setFormValue("modelSelection.provider", providerToUse)
      hasUpdatedProvider.current = true
    }

    // Filter models based on agent type and the provider we're using
    const filteredModels = websiteConfig.modelMappings.filter(
      (model) => model.enabled && model.agentType === agentType && model.provider === providerToUse,
    )

    setAvailableModels(filteredModels)

    // If no models are available for any provider with this agent type, show a warning
    if (filteredModels.length === 0) {
      toast({
        title: "No models available",
        description: `No models are configured for ${agentType}. Please add models in settings.`,
        variant: "warning",
      })
    }

    // If the current model is not in the filtered list, select the first available model
    if (filteredModels.length > 0 && !hasUpdatedModel.current) {
      const modelExists = filteredModels.some((model) => model.model === provider)

      if (!modelExists) {
        setFormValue("modelSelection.model", filteredModels[0].model)
        hasUpdatedModel.current = true
      }
    }
  }, [agentType, provider, websiteConfig, setFormValue, toast])

  return { availableModels }
}
