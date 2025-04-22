"use client"

import { DialogFooter } from "@/components/ui/dialog"

import { useState, useEffect } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import {
  Bot,
  PlusCircle,
  Trash2,
  Edit,
  AlertCircle,
  Lock,
  Globe,
  Code,
  FileText,
  Zap,
  Server,
  ExternalLink,
  Cpu,
  AlertTriangle,
  Save,
  RefreshCw,
  Check,
  Workflow,
} from "lucide-react"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"
import type { WebsiteConfig, Agent, ModelMapping } from "@/lib/types"
import {
  getWebsiteConfig,
  updateWebsiteConfig,
  addModelMapping,
  updateModelMapping,
  deleteModelMapping,
  resetUsingDefaultConfig,
} from "@/app/actions/config-actions"
import { getAgents, deleteAgent } from "@/app/actions/agent-actions"
import { useToast } from "@/components/ui/use-toast"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

// Add this function near the top of the file, after the imports
async function debugConfiguration(setConfig, toast) {
  try {
    // Force reset the isUsingDefaults flag
    resetUsingDefaultConfig()

    // Fetch the website config again
    const refreshedConfig = await getWebsiteConfig()

    // Update the state
    setConfig(refreshedConfig)

    toast({
      title: "Configuration Refreshed",
      description: `Using defaults: ${refreshedConfig.isUsingDefaults ? "Yes" : "No"}. Found ${refreshedConfig.modelMappings.length} model mappings.`,
    })
  } catch (error) {
    console.error("Error debugging configuration:", error)
    toast({
      title: "Error",
      description: "Failed to refresh configuration. See console for details.",
      variant: "destructive",
    })
  }
}

export default function SettingsPage() {
  const searchParams = useSearchParams()
  const initialTab = searchParams.get("tab") || "general"
  const [activeTab, setActiveTab] = useState(initialTab)
  const [config, setConfig] = useState<(WebsiteConfig & { isUsingDefaults?: boolean }) | null>(null)
  const [agents, setAgents] = useState<Agent[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const { toast } = useToast()
  const router = useRouter()

  // Model mapping dialog state
  const [isModelDialogOpen, setIsModelDialogOpen] = useState(false)
  const [currentModelMapping, setCurrentModelMapping] = useState<ModelMapping | null>(null)
  const [isEditingModel, setIsEditingModel] = useState(false)
  const [modelFormData, setModelFormData] = useState<Omit<ModelMapping, "id">>({
    agentType: "ChatCompletionAgent",
    provider: "AzureOpenAI",
    model: "",
    displayName: "",
    enabled: true,
  })
  const [isModelSaving, setIsModelSaving] = useState(false)

  const [deleteDialogAgentId, setDeleteDialogAgentId] = useState<string | null>(null)

  const isConfigSetUpComplete = () => {
    if (!config) return false
    return config.modelMappings.length > 0
  }

  useEffect(() => {
    const loadData = async () => {
      try {
        const [websiteConfig, agentData] = await Promise.all([getWebsiteConfig(), getAgents()])
        setConfig(websiteConfig)
        setAgents(agentData)
      } catch (error) {
        console.error("Failed to load data:", error)
        toast({
          title: "Error loading data",
          description: "There was a problem loading the configuration. Using default values.",
          variant: "destructive",
        })
      } finally {
        setIsLoading(false)
      }
    }

    loadData()
  }, [toast])

  // Update the handleSave function to ensure it properly refreshes the UI after saving
  const handleSave = async () => {
    if (!config) return

    setIsSaving(true)
    try {
      // Remove the isUsingDefaults flag before saving
      const { isUsingDefaults, ...configToSave } = config

      // Save the config
      await updateWebsiteConfig(configToSave)

      // Add a small delay to ensure the backend has processed the update
      await new Promise((resolve) => setTimeout(resolve, 100))

      // Fetch the fresh config from the backend
      const updatedConfig = await getWebsiteConfig()
      console.log("Updated config after save:", updatedConfig)

      // Update the local state with the fresh data
      setConfig(updatedConfig)

      // Manually trigger a refresh of the header component
      if (typeof window !== "undefined") {
        window.dispatchEvent(new Event("website-config-updated"))
      }

      toast({
        title: "Settings saved",
        description: "Your settings have been saved successfully.",
      })
    } catch (error) {
      console.error("Failed to save settings:", error)
      toast({
        title: "Error",
        description: "Failed to save settings. Please try again.",
        variant: "destructive",
      })
    } finally {
      setIsSaving(false)
    }
  }

  const handleDeleteAgent = async (agentId: string) => {
    setIsDeleting(true)
    try {
      console.log("Deleting agent with ID:", agentId)
      await deleteAgent(agentId)
      setAgents(agents.filter((agent) => agent.id !== agentId))
      toast({
        title: "Agent deleted",
        description: "The agent has been deleted successfully.",
      })
    } catch (error) {
      console.error("Failed to delete agent:", error)
      toast({
        title: "Error",
        description: "Failed to delete agent. Please try again.",
        variant: "destructive",
      })
    } finally {
      setIsDeleting(false)
    }
  }

  const openAddModelDialog = () => {
    setIsEditingModel(false)
    setCurrentModelMapping(null)
    setModelFormData({
      agentType: "ChatCompletionAgent",
      provider: "AzureOpenAI",
      model: "",
      displayName: "",
      enabled: true,
    })
    setIsModelDialogOpen(true)
  }

  const openEditModelDialog = (model: ModelMapping) => {
    setIsEditingModel(true)
    setCurrentModelMapping(model)
    setModelFormData({
      agentType: model.agentType,
      provider: model.provider,
      model: model.model,
      displayName: model.displayName,
      enabled: model.enabled,
    })
    setIsModelDialogOpen(true)
  }

  const handleModelFormChange = (field: keyof Omit<ModelMapping, "id">, value: any) => {
    setModelFormData((prev) => {
      const updated = { ...prev, [field]: value }

      // If agent type is AzureAIAgent, force provider to be AzureAIInference
      if (field === "agentType" && value === "AzureAIAgent") {
        return { ...updated, provider: "AzureAIInference" }
      }

      return updated
    })
  }

  const handleSaveModel = async () => {
    setIsModelSaving(true)
    try {
      if (isEditingModel && currentModelMapping) {
        await updateModelMapping(currentModelMapping.id, modelFormData)
        toast({
          title: "Model mapping updated",
          description: "The model mapping has been updated successfully.",
        })
      } else {
        await addModelMapping(modelFormData)
        toast({
          title: "Model mapping added",
          description: "The new model mapping has been added successfully.",
        })
      }

      // Refresh config data
      const updatedConfig = await getWebsiteConfig()
      setConfig(updatedConfig)
      setIsModelDialogOpen(false)
    } catch (error) {
      console.error("Failed to save model mapping:", error)
      toast({
        title: "Error",
        description: "Failed to save model mapping. Please try again.",
        variant: "destructive",
      })
    } finally {
      setIsModelSaving(false)
    }
  }

  const handleDeleteModel = async (id: string) => {
    try {
      await deleteModelMapping(id)

      // Refresh config data
      const updatedConfig = await getWebsiteConfig()
      setConfig(updatedConfig)

      toast({
        title: "Model mapping deleted",
        description: "The model mapping has been deleted successfully.",
      })
    } catch (error) {
      console.error("Failed to delete model mapping:", error)
      toast({
        title: "Error",
        description: "Failed to delete model mapping. Please try again.",
      })
    }
  }

  if (isLoading) {
    return (
      <div className="container mx-auto py-10">
        <div className="flex items-center justify-center h-64">
          <p className="text-muted-foreground">Loading settings...</p>
        </div>
      </div>
    )
  }

  if (!config) {
    return (
      <div className="container mx-auto py-10">
        <div className="flex items-center justify-center h-64">
          <p className="text-destructive">Failed to load settings. Please refresh the page.</p>
        </div>
      </div>
    )
  }

  const renderModelsContent = () => {
    return (
      <>
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold">Model Management</h2>
          <Button onClick={openAddModelDialog}>
            <PlusCircle className="mr-2 h-4 w-4" />
            Add Model Mapping
          </Button>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Available Model Mappings</CardTitle>
            <CardDescription>Configure which models are available for each agent type and provider.</CardDescription>
          </CardHeader>
          <CardContent>
            {config.modelMappings.length === 0 ? (
              <div className="text-center p-6 border border-dashed rounded-lg">
                {config.isUsingDefaults ? (
                  <div className="space-y-4">
                    <AlertCircle className="h-12 w-12 text-amber-500 mx-auto" />
                    <p className="text-muted-foreground">
                      No model mappings are configured. You need to add at least one model mapping before creating
                      agents.
                    </p>
                    <Button onClick={openAddModelDialog} className="mt-2">
                      <PlusCircle className="mr-2 h-4 w-4" />
                      Add Your First Model
                    </Button>
                  </div>
                ) : (
                  <p className="text-muted-foreground">
                    No model mappings configured. Add your first model mapping to get started.
                  </p>
                )}
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Agent Type</TableHead>
                    <TableHead>Provider</TableHead>
                    <TableHead>Model</TableHead>
                    <TableHead>Display Name</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {config.modelMappings.map((model) => (
                    <TableRow key={model.id}>
                      <TableCell>
                        <Badge variant={model.agentType === "AzureAIAgent" ? "blue" : "default"}>
                          {model.agentType === "AzureAIAgent" ? "Azure AI Agent" : "Chat Completion Agent"}
                        </Badge>
                      </TableCell>
                      <TableCell>{model.provider}</TableCell>
                      <TableCell>{model.model}</TableCell>
                      <TableCell>{model.displayName}</TableCell>
                      <TableCell>
                        <Badge variant={model.enabled ? "success" : "secondary"}>
                          {model.enabled ? "Enabled" : "Disabled"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Button variant="ghost" size="sm" onClick={() => openEditModelDialog(model)}>
                            <Edit className="h-4 w-4" />
                          </Button>
                          <AlertDialog
                            open={deleteDialogAgentId === model.id}
                            onOpenChange={(open) => {
                              if (!open) setDeleteDialogAgentId(null)
                            }}
                          >
                            <AlertDialogTrigger asChild>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="text-destructive"
                                onClick={() => setDeleteDialogAgentId(model.id)}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                              <AlertDialogHeader>
                                <AlertDialogTitle>Delete Model Mapping</AlertDialogTitle>
                                <AlertDialogDescription>
                                  Are you sure you want to delete this model mapping? This action cannot be undone.
                                </AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel onClick={() => setDeleteDialogAgentId(null)}>
                                  Cancel
                                </AlertDialogCancel>
                                <AlertDialogAction
                                  onClick={() => {
                                    if (deleteDialogAgentId) {
                                      handleDeleteModel(deleteDialogAgentId)
                                      setDeleteDialogAgentId(null)
                                    }
                                  }}
                                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                >
                                  Delete
                                </AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </>
    )
  }

  const renderContent = () => {
    switch (activeTab) {
      case "general":
        return (
          <Card>
            <CardHeader>
              <CardTitle>General Settings</CardTitle>
              <CardDescription>Configure general settings for the AI Agents Showcase.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="website-name">Website Name</Label>
                  <Input
                    id="website-name"
                    value={config.name}
                    onChange={(e) => setConfig({ ...config, name: e.target.value })}
                  />
                  <p className="text-sm text-muted-foreground">
                    This name will be displayed in the header of the website.
                  </p>
                </div>
                <div className="space-y-4 mt-4">
                  <Label htmlFor="hidden-agents">Hide Agents From Sidebar Menu</Label>

                  {agents.length === 0 ? (
                    <div className="text-sm text-muted-foreground p-4 border rounded-md bg-muted/20">
                      No agents available. Create agents first.
                    </div>
                  ) : (
                    <div className="border rounded-md divide-y">
                      {agents.map((agent) => (
                        <div key={agent.id} className="flex items-center space-x-3 p-3 hover:bg-muted/20">
                          <div
                            className="flex items-center h-5 w-5 cursor-pointer"
                            onClick={() => {
                              setConfig((prev) => {
                                const current = prev.menuHiddenAgentIds || []
                                return {
                                  ...prev,
                                  menuHiddenAgentIds: current.includes(agent.id)
                                    ? current.filter((id) => id !== agent.id)
                                    : [...current, agent.id],
                                }
                              })
                            }}
                          >
                            {(config.menuHiddenAgentIds || []).includes(agent.id) ? (
                              <div className="h-5 w-5 rounded-sm bg-primary flex items-center justify-center">
                                <Check className="h-3.5 w-3.5 text-primary-foreground" />
                              </div>
                            ) : (
                              <div className="h-5 w-5 rounded-sm border border-primary/50" />
                            )}
                          </div>
                          <div className="flex items-center gap-2 flex-1">
                            {agent.tools && agent.tools.some((tool) => tool.type === "Agent") ? (
                              <Workflow className="h-4 w-4 text-muted-foreground" />
                            ) : (
                              <Bot className="h-4 w-4 text-muted-foreground" />
                            )}
                            <span>{agent.name}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {agents.length > 0 && config.menuHiddenAgentIds && config.menuHiddenAgentIds.length > 0 && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="mt-2"
                      onClick={() => setConfig({ ...config, menuHiddenAgentIds: [] })}
                    >
                      Show all agents
                    </Button>
                  )}

                  <p className="text-sm text-muted-foreground">
                    Selected agents will be hidden from the sidebar menu, but still accessible via direct URL.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        )

      case "models":
        return renderModelsContent()

      case "agents":
        return (
          <>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold">Manage Agents</h2>
              <Button
                onClick={() => router.push("/agents/new")}
                disabled={config.isUsingDefaults && config.modelMappings.length === 0}
                title={
                  config.isUsingDefaults && config.modelMappings.length === 0
                    ? "Add model mappings first before creating agents"
                    : undefined
                }
              >
                <PlusCircle className="mr-2 h-4 w-4" />
                Create New Agent
              </Button>
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {agents.length === 0 ? (
                <Card className="col-span-full">
                  <CardContent className="flex flex-col items-center justify-center p-6">
                    <AlertCircle className="h-10 w-10 text-muted-foreground mb-2" />
                    {config.isUsingDefaults && config.modelMappings.length === 0 ? (
                      <>
                        <p className="text-center text-muted-foreground mb-2">
                          Before creating agents, you need to add model mappings.
                        </p>
                        <Button onClick={() => setActiveTab("models")} variant="outline">
                          Go to Model Management
                        </Button>
                      </>
                    ) : (
                      <p className="text-center text-muted-foreground">
                        No agents found. Create your first agent to get started.
                      </p>
                    )}
                  </CardContent>
                </Card>
              ) : (
                agents.map((agent) => (
                  <Card key={agent.id}>
                    <CardHeader className="pb-2">
                      <div className="flex items-center gap-2">
                        {agent.tools && agent.tools.some((tool) => tool.type === "Agent") ? (
                          <Workflow className="h-5 w-5 text-primary" />
                        ) : (
                          <Bot className="h-5 w-5 text-primary" />
                        )}
                        <CardTitle className="text-lg">{agent.name}</CardTitle>
                      </div>
                      <CardDescription className="line-clamp-2">
                        {agent.systemPrompt.substring(0, 100)}
                        {agent.systemPrompt.length > 100 ? "..." : ""}
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="pb-2">
                      <div className="flex flex-wrap gap-2 text-xs">
                        <div className="bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-300 px-2 py-1 rounded-md flex items-center">
                          <Cpu className="h-3.5 w-3.5 mr-1.5" />
                          {agent.agentType === "AzureAIAgent" ? "Azure AI Agent" : "Chat Completion"}
                        </div>
                        <div className="bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300 px-2 py-1 rounded-md">
                          {agent.modelSelection.provider}: {agent.modelSelection.model}
                        </div>
                        {agent.codeInterpreter && (
                          <div className="bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300 px-2 py-1 rounded-md flex items-center">
                            <Code className="h-3.5 w-3.5 mr-1.5" />
                            Code Interpreter
                          </div>
                        )}
                        {agent.fileUpload && (
                          <div className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300 px-2 py-1 rounded-md flex items-center">
                            <FileText className="h-3.5 w-3.5 mr-1.5" />
                            File Upload
                          </div>
                        )}
                        {agent.tools.length > 0 && (
                          <div className="bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300 px-2 py-1 rounded-md flex items-center">
                            <Zap className="h-3.5 w-3.5 mr-1.5" />
                            {agent.tools.length} {agent.tools.length === 1 ? "Tool" : "Tools"}
                          </div>
                        )}
                      </div>
                    </CardContent>
                    <CardFooter className="flex justify-between pt-2">
                      <Button variant="outline" size="sm" onClick={() => router.push(`/agents/${agent.id}/edit`)}>
                        <Edit className="h-4 w-4 mr-1" />
                        Edit
                      </Button>
                      <AlertDialog
                        open={deleteDialogAgentId === agent.id}
                        onOpenChange={(open) => {
                          if (!open) setDeleteDialogAgentId(null)
                        }}
                      >
                        <AlertDialogTrigger asChild>
                          <Button
                            variant="outline"
                            size="sm"
                            className="text-destructive"
                            onClick={() => setDeleteDialogAgentId(agent.id)}
                          >
                            <Trash2 className="h-4 w-4 mr-1" />
                            Delete
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Are you sure?</AlertDialogTitle>
                            <AlertDialogDescription>
                              This action cannot be undone. This will permanently delete the agent and all associated
                              data.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel onClick={() => setDeleteDialogAgentId(null)}>Cancel</AlertDialogCancel>
                            <AlertDialogAction
                              onClick={() => {
                                if (deleteDialogAgentId) {
                                  handleDeleteAgent(deleteDialogAgentId)
                                  setDeleteDialogAgentId(null)
                                }
                              }}
                              disabled={isDeleting}
                              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                            >
                              {isDeleting ? "Deleting..." : "Delete"}
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </CardFooter>
                  </Card>
                ))
              )}
            </div>
          </>
        )

      case "authentication":
        return (
          <Card>
            <CardHeader>
              <CardTitle>Authentication Settings</CardTitle>
              <CardDescription>Configure authentication settings for the AI Agents Showcase.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center justify-between space-x-2">
                  <div className="space-y-0.5">
                    <Label htmlFor="auth-enabled">Enable Authentication</Label>
                    <p className="text-sm text-muted-foreground">
                      Enable Microsoft Authentication Library (MSAL) for user authentication.
                    </p>
                  </div>
                  <Switch
                    id="auth-enabled"
                    checked={config.authenticationEnabled}
                    onCheckedChange={(checked) => setConfig({ ...config, authenticationEnabled: checked })}
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        )

      default:
        return <div>Select a settings category</div>
    }
  }

  return (
    <div className="flex h-full">
      {/* Left Navigation Menu */}
      <div className="w-64 border-r bg-background h-full flex flex-col">
        <div className="p-4 border-b">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Settings</h2>
        </div>
        <ScrollArea className="flex-1">
          <div className="p-2">
            <button
              onClick={() => setActiveTab("general")}
              className={cn(
                "flex items-center w-full px-3 py-2 rounded-md text-sm mb-1",
                activeTab === "general"
                  ? "bg-primary/10 text-primary font-medium"
                  : "hover:bg-primary/5 hover:text-primary",
              )}
            >
              <Globe className="mr-2 h-4 w-4" />
              <span>General</span>
            </button>
            <button
              onClick={() => setActiveTab("models")}
              className={cn(
                "flex items-center w-full px-3 py-2 rounded-md text-sm mb-1",
                activeTab === "models"
                  ? "bg-primary/10 text-primary font-medium"
                  : "hover:bg-primary/5 hover:text-primary",
              )}
            >
              <Server className="mr-2 h-4 w-4" />
              <span>Model Management</span>
            </button>
            <button
              onClick={() => setActiveTab("agents")}
              className={cn(
                "flex items-center w-full px-3 py-2 rounded-md text-sm mb-1",
                activeTab === "agents"
                  ? "bg-primary/10 text-primary font-medium"
                  : "hover:bg-primary/5 hover:text-primary",
              )}
            >
              <Bot className="mr-2 h-4 w-4" />
              <span>Manage Agents</span>
            </button>
            <button
              onClick={() => setActiveTab("authentication")}
              className={cn(
                "flex items-center w-full px-3 py-2 rounded-md text-sm mb-1",
                activeTab === "authentication"
                  ? "bg-primary/10 text-primary font-medium"
                  : "hover:bg-primary/5 hover:text-primary",
              )}
            >
              <Lock className="mr-2 h-4 w-4" />
              <span>Authentication</span>
            </button>
          </div>
        </ScrollArea>
      </div>

      {/* Content Area */}
      <div className="flex-1 p-6 overflow-auto">
        <h1 className="text-2xl font-bold mb-6">Settings</h1>

        {/* Add notification for default configuration */}
        {config.isUsingDefaults && (
          <Alert
            variant="warning"
            className="mb-6 bg-amber-50 border-amber-200 dark:bg-amber-900/20 dark:border-amber-800"
          >
            <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400" />
            <AlertTitle className="text-amber-800 dark:text-amber-300">Using Default Configuration</AlertTitle>
            <AlertDescription className="text-amber-700 dark:text-amber-400">
              You are currently using default configuration values. These changes will not persist unless you save them.
              {process.env.AZURE_APP_CONFIG_CONNECTION_STRING
                ? " Your Azure App Configuration is connected but hasn't been initialized yet. Settings will be stored with the 'ai-agent-config' label."
                : " No Azure App Configuration connection string was found."}
            </AlertDescription>
            <div className="mt-2 flex gap-2">
              <Button
                variant="outline"
                className="bg-white border-amber-200 text-amber-700 hover:bg-amber-100 dark:bg-amber-900/30 dark:border-amber-800 dark:text-amber-300 dark:hover:bg-amber-900/50"
                onClick={handleSave}
              >
                <Save className="h-4 w-4 mr-2" />
                Initialize Configuration
              </Button>
              <Button
                variant="outline"
                className="bg-white border-amber-200 text-amber-700 hover:bg-amber-100 dark:bg-amber-900/30 dark:border-amber-800 dark:text-amber-300 dark:hover:bg-amber-900/50"
                onClick={() => debugConfiguration(setConfig, toast)}
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Refresh Configuration
              </Button>
            </div>
          </Alert>
        )}

        <div className="space-y-4">
          {renderContent()}

          {activeTab === "general" || activeTab === "authentication" ? (
            <div className="flex justify-end mt-6">
              <Button onClick={handleSave} disabled={isSaving}>
                {isSaving ? "Saving..." : "Save Settings"}
              </Button>
            </div>
          ) : null}
        </div>
      </div>

      {/* Model Mapping Dialog */}
      <Dialog open={isModelDialogOpen} onOpenChange={setIsModelDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{isEditingModel ? "Edit Model Mapping" : "Add Model Mapping"}</DialogTitle>
            <DialogDescription>
              {isEditingModel
                ? "Update the model mapping details below."
                : "Configure a new model mapping for agent creation."}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="agent-type">Agent Type</Label>
              <Select
                value={modelFormData.agentType}
                onValueChange={(value) => handleModelFormChange("agentType", value)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select agent type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="AzureAIAgent">Azure AI Agent</SelectItem>
                  <SelectItem value="ChatCompletionAgent">Chat Completion Agent</SelectItem>
                </SelectContent>
              </Select>
              {modelFormData.agentType === "AzureAIAgent" && (
                <p className="text-xs text-muted-foreground">Azure AI Agent has limited model support.</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="provider">Provider</Label>
              <Select
                value={modelFormData.provider}
                onValueChange={(value) => handleModelFormChange("provider", value)}
                disabled={modelFormData.agentType === "AzureAIAgent"}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select provider" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="AzureOpenAI">Azure OpenAI</SelectItem>
                  <SelectItem value="AzureAIInference">Azure AI Inference</SelectItem>
                </SelectContent>
              </Select>
              {modelFormData.agentType === "AzureAIAgent" && (
                <p className="text-xs text-muted-foreground">
                  Azure AI Agent requires Azure AI Inference as the provider.
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="model">Model</Label>
              <Input
                id="model"
                value={modelFormData.model}
                onChange={(e) => handleModelFormChange("model", e.target.value)}
                placeholder="e.g., gpt-4o, phi-3"
              />
              {modelFormData.agentType === "AzureAIAgent" && (
                <div className="flex items-center gap-1 text-xs text-blue-600 mt-1">
                  <ExternalLink className="h-3 w-3" />
                  <a
                    href="https://learn.microsoft.com/en-us/azure/ai-services/agents/concepts/model-region-support"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hover:underline"
                  >
                    View supported models for Azure AI Agent
                  </a>
                </div>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="display-name">Display Name</Label>
              <Input
                id="display-name"
                value={modelFormData.displayName}
                onChange={(e) => handleModelFormChange("displayName", e.target.value)}
                placeholder="e.g., GPT-4o, Phi-3"
              />
              <p className="text-xs text-muted-foreground">The name that will be displayed to users in the UI.</p>
            </div>

            <div className="flex items-center space-x-2">
              <Switch
                id="enabled"
                checked={modelFormData.enabled}
                onCheckedChange={(checked) => handleModelFormChange("enabled", checked)}
              />
              <Label htmlFor="enabled">Enabled</Label>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsModelDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSaveModel}
              disabled={isModelSaving || !modelFormData.model || !modelFormData.displayName}
            >
              {isModelSaving ? "Saving..." : isEditingModel ? "Update" : "Add"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
