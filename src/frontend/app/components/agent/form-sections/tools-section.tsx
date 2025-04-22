"use client"

import { useState } from "react"
import { FormField, FormItem, FormLabel, FormControl, FormDescription, FormMessage } from "@/components/ui/form"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea-fixed"
import { Switch } from "@/components/ui/switch"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import {
  FileText,
  Plus,
  Trash,
  HelpCircle,
  CheckCircle,
  XCircle,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Lock,
} from "lucide-react"
import SecureInput from "../ui/secure-input"
import { validateOpenApiSpec } from "@/app/actions/agent-actions"
import { useToast } from "@/components/ui/use-toast"
import type { UseFormReturn } from "react-hook-form"
import type { AgentFormValues } from "../utils/form-utils"

interface ToolsSectionProps {
  form: UseFormReturn<AgentFormValues>
  isAuthEnabled: boolean
  availableAgents: any[]
  isLoadingAgents: boolean
  onViewSpec: (index: number, format: "json" | "yaml") => void
}

export default function ToolsSection({
  form,
  isAuthEnabled,
  availableAgents,
  isLoadingAgents,
  onViewSpec,
}: ToolsSectionProps) {
  const { toast } = useToast()
  const [validatingTools, setValidatingTools] = useState<Record<number, boolean>>({})
  const [validatedSpecs, setValidatedSpecs] = useState<
    Record<number, { success: boolean; data?: any; error?: string; format?: "json" | "yaml"; title?: string }>
  >({})
  const [expandedSpecs, setExpandedSpecs] = useState<Record<number, boolean>>({})

  const watchToolTypes = form.watch("tools")

  const addTool = () => {
    const currentTools = form.getValues("tools")
    form.setValue("tools", [
      ...currentTools,
      {
        type: "OpenAPI",
        id: `tool_${currentTools.length + 1}`,
        name: `New Tool`,
        specUrl: "",
        authentications: [
          {
            type: "Anonymous",
          },
        ],
      },
    ])
  }

  const addAuthentication = (toolIndex: number) => {
    const currentAuthentications = form.getValues(`tools.${toolIndex}.authentications`) || []
    form.setValue(`tools.${toolIndex}.authentications`, [
      ...currentAuthentications,
      {
        type: "Header",
        headerName: "Ocp-Apim-Subscription-Key",
        headerValue: "",
      },
    ])
  }

  const removeAuthentication = (toolIndex: number, authIndex: number) => {
    const currentAuthentications = form.getValues(`tools.${toolIndex}.authentications`) || []
    if (currentAuthentications.length <= 1) {
      // Don't remove the last authentication method, just reset it to Anonymous
      form.setValue(`tools.${toolIndex}.authentications.0`, {
        type: "Anonymous",
      })
    } else {
      form.setValue(
        `tools.${toolIndex}.authentications`,
        currentAuthentications.filter((_, i) => i !== authIndex),
      )
    }
  }

  const removeTool = (index: number) => {
    const currentTools = form.getValues("tools")
    form.setValue(
      "tools",
      currentTools.filter((_, i) => i !== index),
    )

    // Clean up validation state
    const newValidatingTools = { ...validatingTools }
    delete newValidatingTools[index]
    setValidatingTools(newValidatingTools)

    const newValidatedSpecs = { ...validatedSpecs }
    delete newValidatedSpecs[index]
    setValidatedSpecs(newValidatedSpecs)

    const newExpandedSpecs = { ...expandedSpecs }
    delete newExpandedSpecs[index]
    setExpandedSpecs(newExpandedSpecs)
  }

  const validateSpec = async (index: number) => {
    const tool = form.getValues(`tools.${index}`)
    if (!tool.specUrl) {
      toast({
        title: "Validation Error",
        description: "Please enter a URL for the OpenAPI specification.",
        variant: "destructive",
      })
      return
    }

    setValidatingTools({ ...validatingTools, [index]: true })
    try {
      // Show a toast to indicate validation is in progress
      toast({
        title: "Validating OpenAPI Spec",
        description: "Fetching and validating the specification...",
      })

      // Directly validate the OpenAPI spec
      const authentications = tool.authentications || []
      console.log(`Validating spec at ${tool.specUrl} with authentications:`, authentications)

      const result = await validateOpenApiSpec(tool.specUrl, authentications)
      console.log("Validation result:", result)

      // Store the spec data in the form for later use
      if (result.success && result.data) {
        form.setValue(`tools.${index}.specData`, result.data)
      }

      setValidatedSpecs({ ...validatedSpecs, [index]: result })

      if (result.success) {
        // Auto-populate the tool name with the OpenAPI spec title if available
        if (result.title && (!tool.name || tool.name === `New Tool` || tool.name === `Tool ${index + 1}`)) {
          form.setValue(`tools.${index}.name`, result.title)
        }

        toast({
          title: "Validation Successful",
          description: `The OpenAPI specification (${result.format?.toUpperCase() || "JSON"} format) is valid and accessible.`,
        })
        // Auto-expand the spec details
        setExpandedSpecs({ ...expandedSpecs, [index]: true })
      } else {
        toast({
          title: "Validation Failed",
          description: result.error || "Failed to validate the OpenAPI specification.",
          variant: "destructive",
        })
      }
    } catch (error) {
      console.error("Error validating spec:", error)
      setValidatedSpecs({
        ...validatedSpecs,
        [index]: {
          success: false,
          error:
            "An unexpected error occurred during validation: " +
            (error instanceof Error ? error.message : String(error)),
        },
      })
      toast({
        title: "Validation Error",
        description: "An unexpected error occurred during validation. See console for details.",
        variant: "destructive",
      })
    } finally {
      setValidatingTools({ ...validatingTools, [index]: false })
    }
  }

  // Toggle expanded state for spec details
  const toggleSpecDetails = (index: number) => {
    setExpandedSpecs({
      ...expandedSpecs,
      [index]: !expandedSpecs[index],
    })
  }

  return (
    <Card className="border-amber-200 dark:border-amber-900">
      <CardHeader className="bg-amber-50 dark:bg-amber-950/30 rounded-t-lg">
        <CardTitle className="flex items-center gap-2">
          <FileText className="h-5 w-5 text-amber-600 dark:text-amber-400" />
          Tools Configuration
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-6">
        {/* Display Function Call Status setting */}
        <FormField
          control={form.control}
          name="displayFunctionCallStatus"
          render={({ field }) => (
            <FormItem className="flex flex-row items-center justify-between rounded-lg border border-amber-100 dark:border-amber-900 p-4 bg-amber-50/50 dark:bg-amber-950/20 mb-6">
              <div className="space-y-0.5">
                <FormLabel className="text-base text-amber-800 dark:text-amber-300 flex items-center gap-2">
                  Display Function Call Status
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger type="button" onClick={(e) => e.preventDefault()} asChild>
                        <span className="cursor-help">
                          {" "}
                          <HelpCircle className="h-4 w-4 text-amber-600/70 dark:text-amber-400/70" />
                        </span>
                      </TooltipTrigger>
                      <TooltipContent>
                        <p className="max-w-xs">
                          When enabled, the UI will display real-time updates about function calls being made by the
                          agent. This helps users understand what the agent is doing behind the scenes.
                        </p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </FormLabel>
                <FormDescription className="text-amber-600 dark:text-amber-400">
                  Show real-time function calling status in the chat interface.
                </FormDescription>
              </div>
              <FormControl>
                <Switch
                  checked={field.value}
                  onCheckedChange={field.onChange}
                  className="data-[state=checked]:bg-amber-600 data-[state=checked]:border-amber-800"
                />
              </FormControl>
            </FormItem>
          )}
        />

        <div className="flex items-center justify-between mb-4">
          <p className="text-muted-foreground">Configure tools that your agent can use to perform tasks.</p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={addTool}
            className="bg-amber-50 dark:bg-amber-900/30 border-amber-200 dark:border-amber-800 text-amber-700 dark:text-amber-300 hover:bg-amber-100 dark:hover:bg-amber-900/50"
          >
            <Plus className="h-4 w-4 mr-1" />
            Add Tool
          </Button>
        </div>

        <div className="space-y-6">
          {watchToolTypes.map((tool, index) => (
            <div
              key={index}
              className="border rounded-lg p-4 border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/20"
            >
              <div className="flex items-center justify-between mb-4">
                <h4 className="font-medium text-amber-800 dark:text-amber-300">{tool.name || `Tool ${index + 1}`}</h4>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => removeTool(index)}
                  className="text-amber-700 dark:text-amber-300 hover:bg-amber-100 dark:hover:bg-amber-900/50"
                >
                  <Trash className="h-4 w-4 mr-1" />
                  Remove
                </Button>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name={`tools.${index}.name`}
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Tool Name</FormLabel>
                      <FormControl>
                        <Input {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name={`tools.${index}.type`}
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Tool Type</FormLabel>
                      <FormControl>
                        <Select onValueChange={field.onChange} defaultValue={field.value}>
                          <SelectTrigger>
                            <SelectValue placeholder="Select tool type" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="OpenAPI">OpenAPI Spec</SelectItem>
                            <SelectItem value="Agent">Agent</SelectItem>
                            <SelectItem value="ModelContextProtocol">Model Context Protocol</SelectItem>
                          </SelectContent>
                        </Select>
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              {tool.type === "OpenAPI" && (
                <>
                  <div className="mt-4">
                    <FormField
                      control={form.control}
                      name={`tools.${index}.specUrl`}
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>OpenAPI Specification URL</FormLabel>
                          <div className="flex gap-2">
                            <FormControl className="flex-1">
                              <Input placeholder="https://example.com/api/openapi.json" {...field} />
                            </FormControl>
                            <Button
                              type="button"
                              variant="secondary"
                              onClick={() => validateSpec(index)}
                              disabled={validatingTools[index] || !field.value}
                              className="whitespace-nowrap"
                            >
                              {validatingTools[index] ? (
                                <div className="flex items-center">
                                  <div className="animate-spin mr-2 h-4 w-4 border-2 border-current border-t-transparent rounded-full"></div>
                                  Validating...
                                </div>
                              ) : validatedSpecs[index]?.success ? (
                                <>
                                  <CheckCircle className="h-4 w-4 mr-1 text-green-600" />
                                  Validated
                                </>
                              ) : (
                                <>Validate</>
                              )}
                            </Button>
                          </div>
                          <FormDescription>
                            Enter the URL to your OpenAPI specification. Both JSON and YAML formats are supported.
                          </FormDescription>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>

                  {/* Validation result */}
                  {validatedSpecs[index] && (
                    <div className="mt-3">
                      {validatedSpecs[index].success ? (
                        <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-md p-3">
                          <div className="flex justify-between items-center">
                            <div className="flex items-center text-green-700 dark:text-green-300">
                              <CheckCircle className="h-4 w-4 mr-2" />
                              <span className="font-medium">
                                OpenAPI Specification is valid ({validatedSpecs[index].format?.toUpperCase() || "JSON"})
                              </span>
                            </div>
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              onClick={() => toggleSpecDetails(index)}
                              className="text-green-700 dark:text-green-300"
                            >
                              {expandedSpecs[index] ? (
                                <ChevronUp className="h-4 w-4" />
                              ) : (
                                <ChevronDown className="h-4 w-4" />
                              )}
                            </Button>
                          </div>

                          {expandedSpecs[index] && validatedSpecs[index].data && (
                            <div className="mt-3 border-t border-green-200 dark:border-green-800 pt-3">
                              <div className="text-sm mb-2">
                                <span className="font-medium">Title:</span>{" "}
                                {validatedSpecs[index].data.info?.title || "Untitled API"}
                              </div>
                              <div className="text-sm mb-2">
                                <span className="font-medium">Version:</span>{" "}
                                {validatedSpecs[index].data.info?.version || "N/A"}
                              </div>
                              {validatedSpecs[index].data.info?.description && (
                                <div className="text-sm mb-2">
                                  <span className="font-medium">Description:</span>{" "}
                                  {validatedSpecs[index].data.info.description}
                                </div>
                              )}

                              <div className="mt-3">
                                <h5 className="text-sm font-medium mb-2">Available Endpoints:</h5>
                                <div className="bg-white dark:bg-green-950/30 rounded-md p-2 max-h-60 overflow-y-auto">
                                  {Object.entries(validatedSpecs[index].data.paths || {}).map(
                                    ([path, methods]: [string, any]) => (
                                      <div
                                        key={path}
                                        className="mb-2 pb-2 border-b border-green-100 dark:border-green-900 last:border-0"
                                      >
                                        <div className="font-mono text-xs">{path}</div>
                                        <div className="flex flex-wrap gap-1 mt-1">
                                          {Object.keys(methods || {}).map((method) => (
                                            <span
                                              key={`${path}-${method}`}
                                              className={`text-xs px-2 py-0.5 rounded-full ${
                                                method === "get"
                                                  ? "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300"
                                                  : method === "post"
                                                    ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
                                                    : method === "put"
                                                      ? "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300"
                                                      : method === "delete"
                                                        ? "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300"
                                                        : "bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-300"
                                              }`}
                                            >
                                              {method.toUpperCase()}
                                            </span>
                                          ))}
                                        </div>
                                        <div className="mt-1 text-xs text-muted-foreground">
                                          {methods.get?.summary ||
                                            methods.post?.summary ||
                                            methods.put?.summary ||
                                            methods.delete?.summary ||
                                            ""}
                                        </div>
                                      </div>
                                    ),
                                  )}
                                  {Object.keys(validatedSpecs[index].data.paths || {}).length === 0 && (
                                    <div className="text-sm text-muted-foreground p-2">
                                      No endpoints found in the OpenAPI specification.
                                    </div>
                                  )}
                                </div>
                              </div>

                              <div className="mt-3 flex justify-end">
                                <Button
                                  type="button"
                                  variant="outline"
                                  size="sm"
                                  className="text-green-700 dark:text-green-300 border-green-200 dark:border-green-800"
                                  onClick={() => onViewSpec(index, validatedSpecs[index].format || "json")}
                                >
                                  <ExternalLink className="h-3.5 w-3.5 mr-1" />
                                  View Full Specification
                                </Button>
                              </div>
                            </div>
                          )}
                        </div>
                      ) : (
                        <Alert
                          variant="destructive"
                          className="bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800"
                        >
                          <div className="flex items-center">
                            <XCircle className="h-4 w-4 mr-2" />
                            <span className="font-medium">Validation Failed</span>
                          </div>
                          <AlertDescription className="mt-1">
                            {validatedSpecs[index].error || "Failed to validate the OpenAPI specification."}
                          </AlertDescription>
                        </Alert>
                      )}
                    </div>
                  )}

                  <div className="mt-4 p-3 bg-orange-50 dark:bg-orange-950/30 rounded-lg border border-orange-100 dark:border-orange-900">
                    <div className="flex items-center justify-between mb-2">
                      <h5 className="text-sm font-medium text-orange-700 dark:text-orange-300">Authentication</h5>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => addAuthentication(index)}
                        className="bg-white dark:bg-orange-900/50 border-orange-200 dark:border-orange-800 text-orange-700 dark:text-orange-300 hover:bg-orange-50 dark:hover:bg-orange-900"
                      >
                        <Plus className="h-4 w-4 mr-1" />
                        Add Auth Method
                      </Button>
                    </div>

                    {(tool.authentications || []).map((auth, authIndex) => (
                      <div
                        key={authIndex}
                        className={`p-3 mt-2 rounded-lg ${authIndex > 0 ? "border border-orange-200 dark:border-orange-800 bg-white dark:bg-orange-900/20" : ""}`}
                      >
                        {authIndex > 0 && (
                          <div className="flex justify-between items-center mb-2">
                            <h6 className="text-xs font-medium text-orange-700 dark:text-orange-300">
                              Additional Authentication
                            </h6>
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              onClick={() => removeAuthentication(index, authIndex)}
                              className="text-orange-700 dark:text-orange-300 hover:bg-orange-100 dark:hover:bg-orange-900/50 h-7 w-7 p-0"
                            >
                              <Trash className="h-4 w-4" />
                            </Button>
                          </div>
                        )}

                        <div className="grid grid-cols-2 gap-4 mt-2">
                          <FormField
                            control={form.control}
                            name={`tools.${index}.authentications.${authIndex}.type`}
                            render={({ field }) => (
                              <FormItem>
                                <FormLabel>Authentication Type</FormLabel>
                                <FormControl>
                                  <Select onValueChange={field.onChange} defaultValue={field.value}>
                                    <SelectTrigger>
                                      <SelectValue placeholder="Auth type" />
                                    </SelectTrigger>
                                    <SelectContent>
                                      <SelectItem value="Anonymous">Anonymous (No Auth)</SelectItem>
                                      <SelectItem value="Header">Header</SelectItem>
                                      <SelectItem value="EntraID-AppIdentity">Entra ID (App Identity)</SelectItem>
                                      <SelectItem
                                        value="EntraID-OnBehalfOf"
                                        disabled={!isAuthEnabled}
                                        className={!isAuthEnabled ? "opacity-50 cursor-not-allowed" : ""}
                                      >
                                        <div className="flex items-center gap-1">
                                          Entra ID (On-behalf-of)
                                          {!isAuthEnabled && (
                                            <TooltipProvider>
                                              <Tooltip>
                                                <TooltipTrigger>
                                                  <Lock className="h-3.5 w-3.5 text-muted-foreground ml-1" />
                                                </TooltipTrigger>
                                                <TooltipContent>
                                                  <p className="max-w-xs">
                                                    This option requires user authentication to be enabled in website
                                                    settings.
                                                  </p>
                                                </TooltipContent>
                                              </Tooltip>
                                            </TooltipProvider>
                                          )}
                                        </div>
                                      </SelectItem>
                                    </SelectContent>
                                  </Select>
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                        </div>

                        {auth.type === "Header" && (
                          <div className="grid grid-cols-2 gap-4 mt-2">
                            <FormField
                              control={form.control}
                              name={`tools.${index}.authentications.${authIndex}.headerName`}
                              render={({ field }) => (
                                <FormItem>
                                  <FormLabel>Header Name</FormLabel>
                                  <FormControl>
                                    <Input
                                      placeholder="Ocp-Apim-Subscription-Key"
                                      {...field}
                                      value={field.value || ""}
                                    />
                                  </FormControl>
                                  <FormMessage />
                                </FormItem>
                              )}
                            />
                            <FormField
                              control={form.control}
                              name={`tools.${index}.authentications.${authIndex}.headerValue`}
                              render={({ field }) => (
                                <FormItem>
                                  <FormLabel>Header Value</FormLabel>
                                  <FormControl>
                                    <SecureInput
                                      placeholder="Enter header value"
                                      value={field.value || ""}
                                      onChange={field.onChange}
                                    />
                                  </FormControl>
                                  <FormMessage />
                                </FormItem>
                              )}
                            />
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </>
              )}

              {tool.type === "Agent" && (
                <FormField
                  control={form.control}
                  name={`tools.${index}.id`}
                  render={({ field }) => (
                    <FormItem className="mt-4">
                      <FormLabel>Agent</FormLabel>
                      <FormControl>
                        {isLoadingAgents ? (
                          <div className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm animate-pulse">
                            Loading agents...
                          </div>
                        ) : availableAgents.length > 0 ? (
                          <Select onValueChange={field.onChange} defaultValue={field.value} value={field.value}>
                            <SelectTrigger>
                              <SelectValue placeholder="Select an agent" />
                            </SelectTrigger>
                            <SelectContent>
                              {availableAgents.map((agent) => (
                                <SelectItem key={agent.id} value={agent.id}>
                                  {agent.name}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        ) : (
                          <div className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm text-muted-foreground">
                            No other agents available
                          </div>
                        )}
                      </FormControl>
                      <FormDescription>Select an agent to use as a tool.</FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}

              {tool.type === "ModelContextProtocol" && (
                <div className="mt-4 p-3 bg-indigo-50 dark:bg-indigo-950/30 rounded-lg border border-indigo-100 dark:border-indigo-900">
                  <FormField
                    control={form.control}
                    name={`tools.${index}.mcpDefinition`}
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-indigo-700 dark:text-indigo-300">MCP Definition</FormLabel>
                        <FormControl>
                          <Textarea
                            placeholder={`{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": [
        "@playwright/mcp@latest",
        "--headless"
      ]
    }
  }
}`}
                            className="min-h-[150px] font-mono text-sm bg-white dark:bg-indigo-900/20 border-indigo-200 dark:border-indigo-800"
                            {...field}
                          />
                        </FormControl>
                        <FormDescription className="text-indigo-600 dark:text-indigo-400">
                          Define the Model Context Protocol servers and their configuration.
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              )}
            </div>
          ))}

          {watchToolTypes.length === 0 && (
            <div className="text-center p-6 border border-dashed rounded-lg border-amber-200 dark:border-amber-800 bg-amber-50/30 dark:bg-amber-950/10">
              <p className="text-amber-700 dark:text-amber-300">No tools configured. Click "Add Tool" to add a tool.</p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
