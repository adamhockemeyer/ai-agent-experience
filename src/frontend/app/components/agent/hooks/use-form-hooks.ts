"use client"

import type React from "react"

import { useState, useRef, useEffect, useCallback } from "react"
import type { Agent, WebsiteConfig, ModelMapping } from "@/lib/types"
import { getWebsiteConfig } from "@/app/actions/config-actions"
import { getAgents } from "@/app/actions/agent-actions"
import { useToast } from "@/components/ui/use-toast"

/**
 * Custom hook for debounced callbacks
 */
export function useDebounceCallback<T extends (...args: any[]) => any>(
  callback: T,
  delay: number,
): (...args: Parameters<T>) => void {
  const callbackRef = useRef(callback)
  const timeoutRef = useRef<NodeJS.Timeout | null>(null)

  // Update the callback ref when the callback changes
  useEffect(() => {
    callbackRef.current = callback
  }, [callback])

  return useCallback(
    (...args: Parameters<T>) => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
      timeoutRef.current = setTimeout(() => {
        callbackRef.current(...args)
      }, delay)
    },
    [delay],
  )
}

/**
 * Custom hook for safe resize observer that avoids loop errors
 */
export function useSafeResizeObserver<T extends HTMLElement>(
  callback: (entry: ResizeObserverEntry) => void,
): React.RefObject<T> {
  const ref = useRef<T>(null)
  const debouncedCallback = useDebounceCallback(callback, 100)

  useEffect(() => {
    if (!ref.current) return

    let observer: ResizeObserver | null = null
    let animationFrameId: number | null = null

    // Use try-catch to handle any ResizeObserver errors
    try {
      observer = new ResizeObserver((entries) => {
        if (entries[0]) {
          // Cancel any pending animation frame
          if (animationFrameId !== null) {
            window.cancelAnimationFrame(animationFrameId)
          }

          // Use requestAnimationFrame to avoid ResizeObserver loop errors
          animationFrameId = window.requestAnimationFrame(() => {
            try {
              debouncedCallback(entries[0])
            } catch (error) {
              console.error("Error in resize observer callback:", error)
            }
            animationFrameId = null
          })
        }
      })

      observer.observe(ref.current)
    } catch (error) {
      console.error("ResizeObserver error:", error)
    }

    return () => {
      if (observer) {
        observer.disconnect()
      }
      if (animationFrameId !== null) {
        window.cancelAnimationFrame(animationFrameId)
      }
    }
  }, [debouncedCallback])

  return ref
}

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

  useEffect(() => {
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
    if (!currentProviderHasModels && uniqueProviders.length > 0) {
      providerToUse = uniqueProviders[0]
      // Update the provider in the form
      setFormValue("modelSelection.provider", providerToUse)
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
    if (filteredModels.length > 0) {
      const currentModel = provider
      const modelExists = filteredModels.some((model) => model.model === currentModel)

      if (!modelExists) {
        setFormValue("modelSelection.model", filteredModels[0].model)
      }
    }
  }, [agentType, provider, websiteConfig, setFormValue, toast])

  return { availableModels }
}
