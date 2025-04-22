"use client"

import { FormField, FormItem, FormLabel, FormControl, FormDescription, FormMessage } from "@/components/ui/form"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { Bot, Code, HelpCircle } from "lucide-react"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import type { UseFormReturn } from "react-hook-form"
import type { AgentFormValues } from "../utils/form-utils"
import type { WebsiteConfig, ModelMapping } from "@/lib/types"

interface ModelSettingsSectionProps {
  form: UseFormReturn<AgentFormValues>
  websiteConfig: WebsiteConfig | null
  availableModels: ModelMapping[]
}

export default function ModelSettingsSection({ form, websiteConfig, availableModels }: ModelSettingsSectionProps) {
  const watchAgentType = form.watch("agentType")

  // Get available providers based on agent type
  const getAvailableProviders = () => {
    if (!websiteConfig) return []

    // For AzureAIAgent, only AzureAIInference is available
    if (watchAgentType === "AzureAIAgent") {
      // Check if there are any enabled models for AzureAIAgent with AzureAIInference provider
      const hasModels = websiteConfig.modelMappings.some(
        (model) => model.enabled && model.agentType === "AzureAIAgent" && model.provider === "AzureAIInference",
      )

      if (hasModels) {
        return [{ value: "AzureAIInference", label: "Azure AI Inference" }]
      }
      return []
    }

    // For ChatCompletionAgent, get unique providers from model mappings that have enabled models
    const providers = new Set<string>()
    websiteConfig.modelMappings
      .filter((model) => model.enabled && model.agentType === watchAgentType)
      .forEach((model) => providers.add(model.provider))

    return Array.from(providers).map((provider) => ({
      value: provider,
      label: provider === "AzureOpenAI" ? "Azure OpenAI" : "Azure AI Inference",
    }))
  }

  return (
    <>
      {/* Agent Type Selection */}
      <Card className="border-blue-200 dark:border-blue-900">
        <CardHeader className="bg-blue-50 dark:bg-blue-950/30 rounded-t-lg">
          <CardTitle className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-blue-600 dark:text-blue-400" />
            Agent Type
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-6">
          <FormField
            control={form.control}
            name="agentType"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Agent Type</FormLabel>
                <FormControl>
                  <Select onValueChange={field.onChange} defaultValue={field.value}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select agent type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="AzureAIAgent">Azure AI Agent</SelectItem>
                      <SelectItem value="ChatCompletionAgent">Chat Completion Agent</SelectItem>
                    </SelectContent>
                  </Select>
                </FormControl>
                <FormDescription>
                  {field.value === "AzureAIAgent"
                    ? "Azure AI Agent uses Azure AI Inference service with limited model support."
                    : "Chat Completion Agent uses Azure OpenAI service with broader model support."}
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />

          {/* Foundry Agent ID field - only shown for Azure AI Agent */}
          {watchAgentType === "AzureAIAgent" && (
            <FormField
              control={form.control}
              name="foundryAgentId"
              render={({ field }) => (
                <FormItem className="mt-4">
                  <FormLabel className="flex items-center gap-2">
                    AI Foundry Agent ID (Optional)
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger type="button" onClick={(e) => e.preventDefault()} asChild>
                          <span className="cursor-help">
                            <HelpCircle className="h-4 w-4 text-muted-foreground" />
                          </span>
                        </TooltipTrigger>
                        <TooltipContent>
                          <p className="max-w-xs">
                            Optional. If you have an existing agent in the AI Foundry portal, you can reference it here.
                            Leave blank to create a new agent.
                          </p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </FormLabel>
                  <FormControl>
                    <Input placeholder="asst_QHrOPrhJuvk4zPmRkyQ2zNxn" {...field} value={field.value || ""} />
                  </FormControl>
                  <FormDescription>
                    Optional. Enter the ID of an existing agent from the AI Foundry portal.
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
          )}
        </CardContent>
      </Card>

      <Card className="border-purple-200 dark:border-purple-900">
        <CardHeader className="bg-purple-50 dark:bg-purple-950/30 rounded-t-lg">
          <CardTitle className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-purple-600 dark:text-purple-400" />
            Model Selection
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-6">
          <FormField
            control={form.control}
            name="modelSelection.provider"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Model Provider</FormLabel>
                <FormControl>
                  <Select
                    onValueChange={field.onChange}
                    value={field.value}
                    disabled={watchAgentType === "AzureAIAgent"} // Only disable for AzureAIAgent
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select a provider" />
                    </SelectTrigger>
                    <SelectContent>
                      {getAvailableProviders().map((provider) => (
                        <SelectItem key={provider.value} value={provider.value}>
                          {provider.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </FormControl>
                <FormDescription>
                  {watchAgentType === "AzureAIAgent"
                    ? "Azure AI Agent requires Azure AI Inference service."
                    : "Select the model provider for your Chat Completion Agent."}
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="modelSelection.model"
            render={({ field }) => (
              <FormItem className="mt-4">
                <FormLabel>Model</FormLabel>
                <FormControl>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select a model" />
                    </SelectTrigger>
                    <SelectContent>
                      {availableModels.length > 0 ? (
                        availableModels.map((model) => (
                          <SelectItem key={model.id} value={model.model}>
                            {model.displayName}
                          </SelectItem>
                        ))
                      ) : (
                        <SelectItem value="no-models-available" disabled>
                          No models available
                        </SelectItem>
                      )}
                    </SelectContent>
                  </Select>
                </FormControl>
                <FormDescription>
                  {watchAgentType === "AzureAIAgent" ? (
                    <span>
                      Azure AI Agent has limited model support.{" "}
                      <a
                        href="https://learn.microsoft.com/en-us/azure/ai-services/agents/concepts/model-region-support"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:underline"
                      >
                        View supported models
                      </a>
                      .
                    </span>
                  ) : (
                    "Select the AI model to use for this agent."
                  )}
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
        </CardContent>
      </Card>

      <Card className="border-green-200 dark:border-green-900">
        <CardHeader className="bg-green-50 dark:bg-green-950/30 rounded-t-lg">
          <CardTitle className="flex items-center gap-2">
            <Code className="h-5 w-5 text-green-600 dark:text-green-400" />
            Capabilities
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-6">
          <div className="grid grid-cols-2 gap-4">
            <FormField
              control={form.control}
              name="codeInterpreter"
              render={({ field }) => (
                <FormItem className="flex flex-row items-center justify-between rounded-lg border border-purple-100 dark:border-purple-900 p-4 bg-purple-50/50 dark:bg-purple-950/20">
                  <div className="space-y-0.5">
                    <FormLabel className="text-base text-purple-800 dark:text-purple-300">Code Interpreter</FormLabel>
                    <FormDescription className="text-purple-600 dark:text-purple-400">
                      Allow the agent to execute code.
                    </FormDescription>
                  </div>
                  <FormControl>
                    <Switch
                      checked={field.value}
                      onCheckedChange={field.onChange}
                      className="data-[state=checked]:bg-purple-600 data-[state=checked]:border-purple-800"
                    />
                  </FormControl>
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="fileUpload"
              render={({ field }) => (
                <FormItem className="flex flex-row items-center justify-between rounded-lg border border-green-100 dark:border-green-900 p-4 bg-green-50/50 dark:bg-green-950/20">
                  <div className="space-y-0.5">
                    <FormLabel className="text-base text-green-800 dark:text-green-300">File Upload</FormLabel>
                    <FormDescription className="text-green-600 dark:text-green-400">
                      Allow users to upload files.
                    </FormDescription>
                  </div>
                  <FormControl>
                    <Switch
                      checked={field.value}
                      onCheckedChange={field.onChange}
                      className="data-[state=checked]:bg-green-600 data-[state=checked]:border-green-800"
                    />
                  </FormControl>
                </FormItem>
              )}
            />
          </div>

          <FormField
            control={form.control}
            name="maxTurns"
            render={({ field }) => (
              <FormItem className="mt-4">
                <FormLabel>Max Turns</FormLabel>
                <FormControl>
                  <Input
                    type="number"
                    min={1}
                    max={100}
                    {...field}
                    onChange={(e) => field.onChange(Number.parseInt(e.target.value))}
                  />
                </FormControl>
                <FormDescription>The maximum number of tool calls that can be made in a conversation.</FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
        </CardContent>
      </Card>
    </>
  )
}
