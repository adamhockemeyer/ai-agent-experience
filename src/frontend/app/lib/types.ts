export interface Agent {
  id: string
  name: string
  description: string
  systemPrompt: string
  defaultPrompts: string[]
  agentType: "AzureAIAgent" | "ChatCompletionAgent"
  foundryAgentId?: string
  modelSelection: {
    provider: "AzureAIInference" | "AzureOpenAI"
    model: string
  }
  codeInterpreter: boolean
  fileUpload: boolean
  maxTurns: number
  tools: Tool[]
  requireJsonResponse: boolean
  displayFunctionCallStatus: boolean // Add this new field
}

export interface Tool {
  type: "OpenAPI" | "Agent" | "ModelContextProtocol"
  id: string
  name: string
  spec?: string
  specUrl?: string
  mcpDefinition?: string
  authentications?: Authentication[]
}

export interface Authentication {
  type: "Anonymous" | "Header" | "EntraID-AppIdentity" | "EntraID-OnBehalfOf"
  headerName?: string
  headerValue?: string
}

export interface ModelMapping {
  id: string
  agentType: "AzureAIAgent" | "ChatCompletionAgent"
  provider: "AzureAIInference" | "AzureOpenAI"
  model: string
  displayName: string
  enabled: boolean
}

export interface WebsiteConfig {
  name: string
  authenticationEnabled: boolean
  modelMappings: ModelMapping[]
  menuHiddenAgentIds: string[] // Add this new field
}

export interface ChatMessage {
  id: string
  role: "user" | "assistant" | "system"
  content: string
  timestamp: number
  attachments?: Attachment[]
  traceId?: string // Add this field to store the trace ID
}

export interface Attachment {
  id: string
  name: string
  type: string
  url: string
}

export interface ChatResponse {
  id: string
  content: string
  contentType: "text" | "code" | "image" | "iframe" | "error"
  language?: string
  url?: string
}

export interface FeedbackData {
  messageId: string
  rating: "positive" | "negative"
  comment?: string
  traceId?: string
}

// Update the ChatApiRequest interface to remove the system_prompt field
export interface ChatApiRequest {
  session_id: string
  agent_id: string
  input: string
  attachments?: Attachment[]
}
