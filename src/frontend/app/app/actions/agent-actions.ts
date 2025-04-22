"use server"

import type { Agent, Authentication, FeedbackData, Attachment, ChatApiRequest } from "@/lib/types"
import { v4 as uuidv4 } from "uuid"
import { revalidatePath } from "next/cache"
import { getConfigProvider, AGENT_PREFIX } from "@/lib/config/config-factory"

// Get the config provider
const configProvider = getConfigProvider()

export async function getAgents(): Promise<Agent[]> {
  try {
    // Get all agents from the config provider
    const agentConfigs = await configProvider.getAllConfigs<Agent>(AGENT_PREFIX)

    // Convert the object to an array
    return Object.values(agentConfigs)
  } catch (error) {
    console.error("Error getting agents:", error)
    return []
  }
}

export async function getAgent(id: string): Promise<Agent | undefined> {
  try {
    // Get the agent from the config provider
    const agent = await configProvider.getConfig<Agent>(`${AGENT_PREFIX}${id}`)
    return agent || undefined
  } catch (error) {
    console.error(`Error getting agent ${id}:`, error)
    return undefined
  }
}

// Update the createAgent function with a fixed ID generation
export async function createAgent(agent: Omit<Agent, "id">): Promise<Agent> {
  // Generate a unique ID for the agent based on the name
  const name = agent.name || ""
  const id = name
    .toLowerCase()
    .replace(/[^a-z0-9\s_]/g, "") // Remove special characters with a simpler regex
    .replace(/\s+/g, "_") // Replace spaces with underscores

  // If the ID is empty after processing, use a fallback
  const finalId = id || `agent_${uuidv4().substring(0, 8)}`

  const newAgent: Agent = { id: finalId, ...agent }

  try {
    // Save the agent to the config provider
    const success = await configProvider.upsertConfig(`${AGENT_PREFIX}${finalId}`, newAgent, "application/json")

    if (!success) {
      throw new Error("Failed to create agent")
    }

    revalidatePath("/")
    return newAgent
  } catch (error) {
    console.error("Error creating agent:", error)
    throw error
  }
}

export async function updateAgent(id: string, agent: Omit<Agent, "id">): Promise<Agent> {
  const updatedAgent: Agent = { id, ...agent }

  try {
    // Update the agent in the config provider
    const success = await configProvider.upsertConfig(`${AGENT_PREFIX}${id}`, updatedAgent, "application/json")

    if (!success) {
      throw new Error("Failed to update agent")
    }

    revalidatePath("/")
    return updatedAgent
  } catch (error) {
    console.error(`Error updating agent ${id}:`, error)
    throw error
  }
}

export async function deleteAgent(id: string): Promise<void> {
  try {
    // Delete the agent from the config provider
    const success = await configProvider.deleteConfig(`${AGENT_PREFIX}${id}`)

    if (!success) {
      throw new Error("Failed to delete agent")
    }

    revalidatePath("/")
  } catch (error) {
    console.error(`Error deleting agent ${id}:`, error)
    throw error
  }
}

export async function exportAgentConfig(agent: Agent): Promise<{ success: boolean; data: string }> {
  try {
    const configString = JSON.stringify(agent, null, 2)
    return { success: true, data: configString }
  } catch (error) {
    console.error("Error exporting agent config:", error)
    return { success: false, data: "" }
  }
}

export async function validateOpenApiSpec(
  specUrl: string,
  authentications?: Authentication[],
): Promise<{ success: boolean; data?: any; error?: string; format?: "json" | "yaml"; title?: string }> {
  try {
    console.log(`Validating OpenAPI spec at URL: ${specUrl}`)

    // Prepare fetch options with authentication if provided
    const fetchOptions: RequestInit = {
      method: "GET",
      headers: {
        Accept: "application/json, application/yaml, */*",
      },
      // Use longer timeout
      signal: AbortSignal.timeout(30000), // 30 second timeout
    }

    // Add authentication headers if provided
    if (authentications && authentications.length > 0) {
      const headers = new Headers(fetchOptions.headers)

      for (const auth of authentications) {
        if (auth.type === "Header" && auth.headerName && auth.headerValue) {
          console.log(`Adding auth header: ${auth.headerName}`)
          headers.set(auth.headerName, auth.headerValue)
        }
      }

      fetchOptions.headers = headers
    }

    console.log("Fetching spec with options:", JSON.stringify(fetchOptions, null, 2))

    // Fetch the spec
    const response = await fetch(specUrl, fetchOptions)

    if (!response.ok) {
      console.error(`Failed to fetch spec: ${response.status} ${response.statusText}`)
      return {
        success: false,
        error: `Failed to fetch spec from URL: ${response.status} ${response.statusText}. Make sure the URL is accessible and CORS is enabled.`,
      }
    }

    // Get content type to determine format
    const contentType = response.headers.get("content-type") || ""
    console.log(`Content-Type: ${contentType}`)

    let specData: any
    let format: "json" | "yaml" = "json"
    const responseText = await response.text()

    // Try to parse as JSON first
    try {
      specData = JSON.parse(responseText)
      format = "json"
      console.log("Successfully parsed as JSON")
    } catch (jsonError) {
      // If JSON parsing fails, try YAML
      try {
        const jsYaml = await import("js-yaml")
        specData = jsYaml.load(responseText)
        format = "yaml"
        console.log("Successfully parsed as YAML")
      } catch (yamlError) {
        console.error("Failed to parse as JSON or YAML:", yamlError)
        return {
          success: false,
          error: `Failed to parse response as JSON or YAML. Content received: ${responseText.substring(0, 100)}...`,
        }
      }
    }

    if (!specData || typeof specData !== "object") {
      console.error("Spec data is invalid or empty")
      return { success: false, error: "Spec data is invalid or empty." }
    }

    // Basic validation - check for required fields
    if (!specData.openapi && !specData.swagger) {
      console.error("Missing openapi/swagger field")
      return {
        success: false,
        error:
          "Spec is missing required fields (openapi/swagger). This doesn't appear to be a valid OpenAPI specification.",
      }
    }

    if (!specData.info) {
      console.error("Missing info field")
      return {
        success: false,
        error: "Spec is missing the 'info' field. This doesn't appear to be a valid OpenAPI specification.",
      }
    }

    if (!specData.paths) {
      console.error("Missing paths field")
      return {
        success: false,
        error: "Spec is missing the 'paths' field. This doesn't appear to be a valid OpenAPI specification.",
      }
    }

    console.log("OpenAPI spec validation successful")
    return {
      success: true,
      data: specData,
      format: format,
      title: specData.info?.title || undefined,
    }
  } catch (error) {
    console.error("Error validating OpenAPI spec:", error)
    return {
      success: false,
      error: `An error occurred during validation: ${error instanceof Error ? error.message : String(error)}. Check if the URL is accessible.`,
    }
  }
}

export async function submitFeedback(feedback: FeedbackData): Promise<void> {
  // In a real application, you would save the feedback to a database or external source
  console.log("Feedback submitted:", feedback)
}

// Replace the sendMessage function with this simplified version that handles plain text streaming

export async function sendMessage(
  agentId: string,
  message: string,
  attachments: Attachment[] = [],
  sessionId?: string,
): Promise<{ stream: ReadableStream<Uint8Array>; traceId?: string; sessionId: string }> {
  // Get the chat API endpoint from environment variables
  const chatApiEndpoint = process.env.CHAT_API_ENDPOINT

  if (!chatApiEndpoint) {
    // Return an error if the API endpoint is not configured
    return {
      stream: new ReadableStream({
        start(controller) {
          controller.enqueue(new TextEncoder().encode("Error: Chat API endpoint not configured"))
          controller.close()
        },
      }),
      sessionId: uuidv4(), // Generate a session ID even for error cases
    }
  }

  const finalSessionId = sessionId || uuidv4()

  try {
    // Get the agent to access its system prompt
    const agent = await getAgent(agentId)
    if (!agent) {
      throw new Error(`Agent with ID ${agentId} not found`)
    }

    // Create a session ID (could be stored in a more persistent way)
    // const finalSessionId = sessionId || uuidv4()

    // Prepare the request payload - remove system_prompt
    const payload: ChatApiRequest = {
      session_id: finalSessionId,
      agent_id: agentId,
      input: message,
      attachments: attachments.length > 0 ? attachments : undefined,
    }

    console.log(`Sending chat request to ${chatApiEndpoint}/api/chat:`, payload)

    // Make the API call
    const response = await fetch(`${chatApiEndpoint}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    })

    if (!response.ok) {
      throw new Error(`API request failed with status ${response.status}: ${response.statusText}`)
    }

    // Extract the trace ID from the response headers
    const traceId = response.headers.get("x-otel-trace-id") || undefined
    console.log("Received trace ID:", traceId)

    // Check if the response is a stream
    if (response.body) {
      // Return the raw stream - we'll handle the text in the UI
      return { stream: response.body, traceId, sessionId: finalSessionId }
    } else {
      // If the response doesn't have a body, create an error stream
      return {
        stream: new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode("Error: API response did not contain a readable stream"))
            controller.close()
          },
        }),
        sessionId: finalSessionId,
      }
    }
  } catch (error) {
    console.error("Error sending message to API:", error)

    // Return an error stream
    return {
      stream: new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              `Error connecting to chat API: ${error instanceof Error ? error.message : String(error)}`,
            ),
          )
          controller.close()
        },
      }),
      sessionId: finalSessionId, // Use the provided or generated session ID
    }
  }
}
