import { z } from "zod"

/**
 * Generates a valid agent ID from a name by converting to lowercase and replacing spaces with underscores
 */
export function generateAgentId(name: string): string {
  // First convert to lowercase
  const lowercase = name.toLowerCase()
  // Then remove special characters (using a simpler regex)
  const noSpecialChars = lowercase.replace(/[^a-z0-9\s_]/g, "")
  // Finally replace spaces with underscores
  return noSpecialChars.replace(/\s+/g, "_")
}

/**
 * Debounce function to limit how often a function can be called
 */
export function debounce<T extends (...args: any[]) => any>(func: T, wait: number): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout | null = null

  return (...args: Parameters<T>) => {
    if (timeout) clearTimeout(timeout)
    timeout = setTimeout(() => func(...args), wait)
  }
}

/**
 * Zod schema for agent form validation
 */
export const agentFormSchema = z.object({
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
  jsonResponseSchema: z.string().optional().refine((value) => {
    if (!value || value.trim() === "") {
      return true; // Empty is allowed
    }

    try {
      const parsed = JSON.parse(value);

      // Basic validation for structured outputs requirements
      if (typeof parsed !== 'object' || parsed === null) {
        return false;
      }

      if (parsed.type !== 'object') {
        return false;
      }

      if (!parsed.properties || typeof parsed.properties !== 'object') {
        return false;
      }

      if (!parsed.required || !Array.isArray(parsed.required)) {
        return false;
      }

      if (parsed.additionalProperties !== false) {
        return false;
      }

      // Check that all properties are in required array
      const propertyNames = Object.keys(parsed.properties);
      const missingRequired = propertyNames.filter(prop => !parsed.required.includes(prop));
      if (missingRequired.length > 0) {
        return false;
      }

      return true;
    } catch (e) {
      return false;
    }
  }, {
    message: "JSON schema must be valid and comply with structured outputs requirements"
  }),
  displayFunctionCallStatus: z.boolean(),
  // Chat history reduction settings
  enableHistoryReduction: z.boolean(),
  reducerMsgCount: z.number().int().min(1).max(100),
  reducerThreshold: z.number().int().min(0).max(50),
})

export type AgentFormValues = z.infer<typeof agentFormSchema>

// Backward compatibility alias
export const formSchema = agentFormSchema
