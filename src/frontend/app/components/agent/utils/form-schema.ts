import { z } from "zod"

// Form schema for agent form
export const formSchema = z.object({
  name: z.string().min(2, {
    message: "Name must be at least 2 characters.",
  }),
  description: z
    .string()
    .min(10, {
      message: "Description must be at least 10 characters.",
    })
    .max(200, {
      message: "Description must be less than 200 characters.",
    }),
  systemPrompt: z.string().min(10, {
    message: "System prompt must be at least 10 characters.",
  }),
  defaultPrompts: z.array(z.string()),
  agentType: z.enum(["AzureAIAgent", "ChatCompletionAgent"]),
  foundryAgentId: z.string().optional(),
  modelSelection: z.object({
    provider: z.enum(["AzureAIInference", "AzureOpenAI"]),
    model: z.string().min(1, {
      message: "Model must be selected.",
    }),
  }),
  codeInterpreter: z.boolean(),
  fileUpload: z.boolean(),
  maxTurns: z.number().int().min(1).max(100),
  tools: z.array(
    z.object({
      type: z.enum(["OpenAPI", "Agent", "ModelContextProtocol"]),
      id: z.string(),
      name: z.string(),
      specUrl: z.string().optional(),
      mcpDefinition: z.string().optional(),
      authentications: z
        .array(
          z.object({
            type: z.enum(["Anonymous", "Header", "EntraID-AppIdentity", "EntraID-OnBehalfOf"]),
            headerName: z.string().optional(),
            headerValue: z.string().optional(),
          }),
        )
        .optional(),
    }),
  ),
  requireJsonResponse: z.boolean(),
  displayFunctionCallStatus: z.boolean(),
})

export type AgentFormValues = z.infer<typeof formSchema>

// Helper function to generate agent ID from name
export function generateAgentId(name: string): string {
  // First convert to lowercase
  const lowercase = name.toLowerCase()
  // Then remove special characters (using a simpler regex)
  const noSpecialChars = lowercase.replace(/[^a-z0-9\s_]/g, "")
  // Finally replace spaces with underscores
  return noSpecialChars.replace(/\s+/g, "_")
}
