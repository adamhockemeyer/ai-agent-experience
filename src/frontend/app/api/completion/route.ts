import { NextRequest } from 'next/server'

export const maxDuration = 30

export async function POST(req: NextRequest) {
  try {
    // Extract the prompt from the request body (AI SDK sends it as 'prompt')
    const { prompt, agent_id, session_id, attachments = [], ...additionalData } = await req.json()

    // Get the chat API endpoint from environment variables
    const chatApiEndpoint = process.env.CHAT_API_ENDPOINT

    if (!chatApiEndpoint) {
      throw new Error('CHAT_API_ENDPOINT environment variable is not set')
    }

    // If agent_id is not provided in the body, check headers or use default
    const agentId = agent_id || req.headers.get('x-agent-id') || 'default'
    const finalSessionId = session_id || crypto.randomUUID()

    // Prepare the request payload for your Python API
    const requestPayload = {
      session_id: finalSessionId,
      agent_id: agentId,
      input: prompt,
      attachments,
      ...additionalData
    }

    console.log('AI SDK Completion - Sending request to Python API:', {
      url: `${chatApiEndpoint}/chat`,
      payload: requestPayload
    })

    // Make the request to your Python API
    const response = await fetch(`${chatApiEndpoint}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestPayload),
    })

    if (!response.ok) {
      const errorText = await response.text()
      console.error('Python API error response:', errorText)
      throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`)
    }

    // Check if the response is a stream
    if (response.headers.get('content-type')?.includes('text/event-stream')) {
      // Return the stream from your Python API
      // The AI SDK with streamProtocol: 'text' expects a simple text stream
      return new Response(response.body, {
        headers: {
          'Content-Type': 'text/plain; charset=utf-8',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
          // Forward the trace ID if present
          'X-OTel-Trace-ID': response.headers.get('X-OTel-Trace-ID') || '',
          // Forward the session ID back to the client
          'X-Session-ID': finalSessionId,
        },
      })
    } else {
      // If it's not a stream, read the response and return it
      const text = await response.text()
      return new Response(text, {
        headers: {
          'Content-Type': 'text/plain; charset=utf-8',
          'X-Session-ID': finalSessionId,
        },
      })
    }
  } catch (error) {
    console.error('Error in AI SDK completion route:', error)
    return new Response(
      `Error: ${error instanceof Error ? error.message : 'Unknown error occurred'}`,
      {
        status: 500,
        headers: {
          'Content-Type': 'text/plain; charset=utf-8',
        },
      }
    )
  }
}
