"use client"

import React from "react"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { Button } from "@/components/ui/button"
import { Form } from "@/components/ui/form"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { Agent } from "@/lib/types"
import { createAgent, updateAgent, exportAgentConfig } from "@/app/actions/agent-actions"
import { Download } from "lucide-react"
import AgentVisualization from "./agent-visualization"
import { useToast } from "@/components/ui/use-toast"
import { AgentVisualizationErrorBoundary } from "./agent-visualization-error-boundary"
import { useWebsiteConfig } from "@/lib/hooks/use-website-config"
import { useAvailableAgents } from "@/lib/hooks/use-available-agents"
import { useAvailableModels } from "@/lib/hooks/use-available-models"
import { formSchema, type AgentFormValues } from "./utils/form-schema"
import BasicSettingsSection from "./form-sections/basic-settings-section"
import ModelSettingsSection from "./form-sections/model-settings-section"
import ToolsSection from "./form-sections/tools-section"
import { AdvancedSettingsSection } from "./form-sections/advanced-settings-section"
import ExportConfigDialog from "./dialogs/export-config-dialog"
import SpecViewDialog from "./dialogs/spec-view-dialog"

// Global error handler for ResizeObserver errors
if (typeof window !== "undefined") {
  const errorHandler = (event: ErrorEvent) => {
    if (event.message.includes("ResizeObserver") || event.error?.message?.includes("ResizeObserver")) {
      event.preventDefault()
      console.warn("ResizeObserver error suppressed:", event.message)
    }
  }

  window.addEventListener("error", errorHandler)
  window.addEventListener("unhandledrejection", (event) => {
    if (event.reason && event.reason.message && event.reason.message.includes("ResizeObserver")) {
      event.preventDefault()
      console.warn("ResizeObserver promise rejection suppressed:", event.reason.message)
    }
  })
}

interface AgentFormProps {
  agent?: Agent
  isEditing?: boolean
}

export default function AgentForm({ agent, isEditing = false }: AgentFormProps) {
  
  const router = useRouter()
  const { toast } = useToast()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const [exportedConfig, setExportedConfig] = useState<string>("")
  const [isExportDialogOpen, setIsExportDialogOpen] = useState(false)

  // Spec view dialog state
  const [specViewDialogOpen, setSpecViewDialogOpen] = useState(false)
  const [currentSpecIndex, setCurrentSpecIndex] = useState<number | null>(null)
  const [currentSpecData, setCurrentSpecData] = useState<any>(null)
  const [currentSpecUrl, setCurrentSpecUrl] = useState<string>("")
  const [currentSpecTitle, setCurrentSpecTitle] = useState<string>("")
  const [specViewFormat, setSpecViewFormat] = useState<"json" | "yaml">("json")

  // Get website config and available agents
  const { websiteConfig, isLoading: isLoadingConfig } = useWebsiteConfig()
  const { agents: availableAgents, isLoading: isLoadingAgents } = useAvailableAgents(isEditing, agent?.id)

  // Initialize form with default values or agent data
  const form = useForm<AgentFormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: agent || {
      name: "",
      description: "",
      systemPrompt: "",
      defaultPrompts: [""],
      agentType: "ChatCompletionAgent",
      foundryAgentId: "",
      modelSelection: {
        provider: "AzureOpenAI",
        model: "gpt-4o",
      },
      codeInterpreter: false,
      fileUpload: false,
      maxTurns: 10,
      tools: [],
      requireJsonResponse: false,
      displayFunctionCallStatus: false,
    },
  })

  // Watch form values for visualization and conditional rendering
  const watchName = form.watch("name")
  const watchTools = form.watch("tools")
  const watchCodeInterpreter = form.watch("codeInterpreter")
  const watchFileUpload = form.watch("fileUpload")
  const watchAgentType = form.watch("agentType")
  const watchProvider = form.watch("modelSelection.provider")

  // Memoize the setFormValue function to prevent unnecessary re-renders
  const setFormValue = React.useCallback(
    (field: string, value: any) => {
      form.setValue(field as any, value, { shouldValidate: true })
    },
    [form],
  )

  // Get available models based on agent type and provider
  const { availableModels } = useAvailableModels(websiteConfig, watchAgentType, watchProvider, setFormValue)

  // Ensure all tools have authentications array on initial load
  useEffect(() => {
    const tools = form.getValues("tools")
    if (!tools || tools.length === 0) return

    let needsUpdate = false
    const updatedTools = tools.map((tool) => {
      // Convert old authentication object to authentications array if needed
      if (!tool.authentications) {
        needsUpdate = true
        return {
          ...tool,
          authentications: tool.authentication ? [tool.authentication] : [{ type: "Anonymous" }],
        }
      }
      return tool
    })

    if (needsUpdate) {
      form.setValue("tools", updatedTools)
    }
  }, [form])

  // Add more detailed debugging to the form submission process

  // Update the onSubmit function to include more detailed logging and error handling
  async function onSubmit(values: AgentFormValues) {
    console.log("Form submitted with values:", values)
    setIsSubmitting(true)
    try {
      if (isEditing && agent) {
        console.log("Updating existing agent:", agent.id)
        const updatedAgent = await updateAgent(agent.id, values)
        console.log("Agent updated successfully:", updatedAgent)
        toast({
          title: "Success",
          description: "Agent updated successfully.",
        })
        router.push(`/agents/${agent.id}`)
      } else {
        console.log("Creating new agent with name:", values.name)
        const newAgent = await createAgent(values)
        console.log("Agent created successfully:", newAgent)
        toast({
          title: "Success",
          description: "Agent created successfully.",
        })
        router.push(`/agents/${newAgent.id}`)
      }
    } catch (error) {
      console.error("Error saving agent:", error)
      toast({
        title: "Error",
        description: `Failed to save agent: ${error instanceof Error ? error.message : "Unknown error"}`,
        variant: "destructive",
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  // Add a manual form submission function
  const manualSubmit = async () => {
    console.log("Manual form submission triggered")
    // Get current form values
    const values = form.getValues()
    console.log("Current form values:", values)

    // Check form validation
    const isValid = await form.trigger()
    console.log("Form validation result:", isValid)

    if (isValid) {
      // If form is valid, call onSubmit directly
      await onSubmit(values)
    } else {
      // If form is invalid, log the errors
      const errors = form.formState.errors
      console.error("Form validation errors:", errors)
      toast({
        title: "Validation Error",
        description: "Please fix the form errors before submitting.",
        variant: "destructive",
      })
    }
  }

  // Handle exporting agent configuration
  const handleExportConfig = async () => {
    setIsExporting(true)
    try {
      // Get current form values
      const formValues = form.getValues()

      // Create a complete agent object for export
      const agentToExport: Agent = {
        id: isEditing && agent ? agent.id : formValues.name.toLowerCase().replace(/\s+/g, "_"),
        ...formValues,
      }

      // Call the server action to export
      const result = await exportAgentConfig(agentToExport)

      if (result.success) {
        // Set the exported config and open the dialog
        setExportedConfig(result.data)
        setIsExportDialogOpen(true)

        toast({
          title: "Export Successful",
          description: "Agent configuration has been exported successfully.",
        })
      } else {
        throw new Error("Export failed")
      }
    } catch (error) {
      console.error("Error exporting agent config:", error)
      toast({
        title: "Export Failed",
        description: "Failed to export agent configuration. Please try again.",
        variant: "destructive",
      })
    } finally {
      setIsExporting(false)
    }
  }

  // Handle viewing OpenAPI spec
  const handleViewSpec = (index: number, format: "json" | "yaml") => {
    const tool = form.getValues(`tools.${index}`)
    const specData = tool.specData || {}
    const specUrl = tool.specUrl || ""
    const specTitle = tool.name || "OpenAPI Specification"

    setCurrentSpecIndex(index)
    setCurrentSpecData(specData)
    setCurrentSpecUrl(specUrl)
    setCurrentSpecTitle(specTitle)
    setSpecViewFormat(format)
    setSpecViewDialogOpen(true)
  }

  // Check if authentication is enabled
  const isAuthEnabled = websiteConfig?.authenticationEnabled || false

  // Generate agent ID from name
  const generatedId = watchName ? watchName.toLowerCase().replace(/\s+/g, "_") : isEditing && agent ? agent.id : ""

  if (isLoadingConfig) {
    return (
      <div className="container mx-auto py-10">
        <div className="flex items-center justify-center h-64">
          <p className="text-muted-foreground">Loading settings...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2">
        <div className="flex justify-between items-center mb-4">
          <h1 className="text-2xl font-bold">{isEditing ? `Edit Agent: ${agent?.name}` : "Create New Agent"}</h1>
          <Button
            variant="outline"
            size="sm"
            onClick={handleExportConfig}
            disabled={isExporting}
            className="flex items-center gap-2"
          >
            <Download className="h-4 w-4" />
            {isExporting ? "Exporting..." : "Export Agent Config"}
          </Button>
        </div>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8">
            <Tabs defaultValue="basic">
              <TabsList className="grid w-full grid-cols-4">
                <TabsTrigger value="basic">Basic Settings</TabsTrigger>
                <TabsTrigger value="model">Model & Capabilities</TabsTrigger>
                <TabsTrigger value="tools">Tools</TabsTrigger>
                <TabsTrigger value="advanced">Advanced Settings</TabsTrigger>
              </TabsList>

              <TabsContent value="basic" className="space-y-4 mt-4">
                <BasicSettingsSection form={form} />
              </TabsContent>

              <TabsContent value="model" className="space-y-4 mt-4">
                <ModelSettingsSection form={form} websiteConfig={websiteConfig} availableModels={availableModels} />
              </TabsContent>

              <TabsContent value="tools" className="space-y-4 mt-4">
                <ToolsSection
                  form={form}
                  isAuthEnabled={isAuthEnabled}
                  availableAgents={availableAgents}
                  isLoadingAgents={isLoadingAgents}
                  onViewSpec={handleViewSpec}
                />
              </TabsContent>

              <TabsContent value="advanced" className="space-y-4 mt-4">
                <AdvancedSettingsSection form={form} />
              </TabsContent>
            </Tabs>

            <div className="flex justify-end gap-4">
              <Button type="button" variant="outline" onClick={() => router.back()}>
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={isSubmitting}
                className="bg-primary hover:bg-primary/90 font-medium"
                onClick={() => {
                  // Add a click handler to ensure the button is being clicked
                  console.log("Submit button clicked")
                  // Try manual submission as a fallback
                  setTimeout(() => {
                    if (!form.formState.isSubmitting) {
                      console.log("Form not submitting automatically, trying manual submission")
                      manualSubmit()
                    }
                  }, 100)
                }}
              >
                {isSubmitting ? "Saving..." : isEditing ? "Update Agent" : "Create Agent"}
              </Button>
            </div>
          </form>
        </Form>
      </div>

      {/* Visualization column - always visible */}
      <div className="lg:col-span-1">
        <div className="sticky top-6">
          <AgentVisualizationErrorBoundary>
            {/* Wrap the visualization in a div with fixed dimensions to prevent layout shifts */}
            <div style={{ width: "100%", maxWidth: "400px" }}>
              <AgentVisualization
                agentName={watchName}
                agentType={watchAgentType}
                tools={watchTools}
                codeInterpreter={watchCodeInterpreter}
                fileUpload={watchFileUpload}
                displayFunctionCallStatus={form.watch("displayFunctionCallStatus")}
              />
            </div>
          </AgentVisualizationErrorBoundary>
        </div>
      </div>

      {/* Export Config Dialog */}
      <ExportConfigDialog
        isOpen={isExportDialogOpen}
        onOpenChange={setIsExportDialogOpen}
        exportedConfig={exportedConfig}
        agentId={generatedId}
      />

      {/* Spec View Dialog */}
      <SpecViewDialog
        isOpen={specViewDialogOpen}
        onOpenChange={setSpecViewDialogOpen}
        specData={currentSpecData}
        specUrl={currentSpecUrl}
        specTitle={currentSpecTitle}
        initialFormat={specViewFormat}
      />
    </div>
  )
}
