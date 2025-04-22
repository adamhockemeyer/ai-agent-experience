import type { WebsiteConfig, Agent, ModelMapping } from "@/lib/types"

// Mock model mappings
export const mockModelMappings: ModelMapping[] = [
  {
    id: "model_1",
    agentType: "AzureAIAgent",
    provider: "AzureAIInference",
    model: "phi-3",
    displayName: "Phi-3",
    enabled: true,
  },
  {
    id: "model_2",
    agentType: "AzureAIAgent",
    provider: "AzureAIInference",
    model: "llama-3",
    displayName: "Llama 3",
    enabled: true,
  },
  {
    id: "model_3",
    agentType: "ChatCompletionAgent",
    provider: "AzureOpenAI",
    model: "gpt-4o",
    displayName: "GPT-4o",
    enabled: true,
  },
  {
    id: "model_4",
    agentType: "ChatCompletionAgent",
    provider: "AzureOpenAI",
    model: "gpt-4o-mini",
    displayName: "GPT-4o Mini",
    enabled: true,
  },
  {
    id: "model_5",
    agentType: "ChatCompletionAgent",
    provider: "AzureOpenAI",
    model: "gpt-35-turbo",
    displayName: "GPT-3.5 Turbo",
    enabled: true,
  },
  {
    id: "model_6",
    agentType: "ChatCompletionAgent",
    provider: "AzureAIInference",
    model: "phi-3",
    displayName: "Phi-3 (AI Inference)",
    enabled: true,
  },
]

// Default minimal website configuration
export const mockWebsiteConfig: WebsiteConfig = {
  name: "AI Agents Showcase",
  authenticationEnabled: false,
  modelMappings: [], // Empty by default to force setup
  menuHiddenAgentIds: [], // Add this new field with empty array as default
}

// Mock agent data - kept for reference but not used by default
export const mockAgents: Agent[] = [
  {
    id: "agent1",
    name: "Data Analysis Agent",
    description: "An agent that helps with data analysis tasks",
    systemPrompt: "You are a data analysis expert. Help users analyze and visualize their data.",
    defaultPrompts: ["Analyze this dataset", "Create a visualization for my data"],
    agentType: "AzureAIAgent",
    foundryAgentId: "asst_QHrOPrhJuvk4zPmRkyQ2zNxn",
    modelSelection: {
      provider: "AzureOpenAI",
      model: "gpt-4o",
    },
    codeInterpreter: true,
    fileUpload: true,
    maxTurns: 10,
    tools: [
      {
        type: "OpenAPI",
        id: "tool_1",
        name: "Data API",
        specUrl: "https://example.com/api/openapi.json",
        authentications: [
          {
            type: "Anonymous",
          },
        ],
      },
    ],
    requireJsonResponse: false,
  },
  {
    id: "agent2",
    name: "Document Assistant",
    description: "An agent that helps with document processing",
    systemPrompt: "You are a document processing assistant. Help users extract and analyze information from documents.",
    defaultPrompts: ["Extract text from this PDF", "Summarize this document"],
    agentType: "ChatCompletionAgent",
    modelSelection: {
      provider: "AzureOpenAI",
      model: "gpt-35-turbo",
    },
    codeInterpreter: false,
    fileUpload: true,
    maxTurns: 5,
    tools: [],
    requireJsonResponse: false,
  },
]
