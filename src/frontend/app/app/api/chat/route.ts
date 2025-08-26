import { NextRequest } from 'next/server'

export const maxDuration = 30

export async function POST(req: NextRequest) {
    try {
        const { prompt, agent_id, session_id, attachments = [] } = await req.json()

        // Get the chat API endpoint from environment variables
        const chatApiEndpoint = process.env.CHAT_API_ENDPOINT

        if (!chatApiEndpoint) {
            throw new Error('CHAT_API_ENDPOINT environment variable is not set')
        }

        // Prepare the request payload for your Python API
        const requestPayload = {
            session_id: session_id || crypto.randomUUID(),
            agent_id,
            input: prompt,
            attachments
        }

        // Make the request to your Python API
        const response = await fetch(`${chatApiEndpoint}/api/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestPayload),
        })

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`)
        }

        // Check if the response is a stream
        if (response.headers.get('content-type')?.includes('text/event-stream')) {
            // Return the stream from your Python API
            // The AI SDK expects a simple text stream, which is what your Python API provides
            return new Response(response.body, {
                headers: {
                    'Content-Type': 'text/plain; charset=utf-8',
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive',
                    // Forward the trace ID if present
                    'X-OTel-Trace-ID': response.headers.get('X-OTel-Trace-ID') || '',
                },
            })
        } else {
            // If it's not a stream, read the response and return it
            const text = await response.text()
            return new Response(text, {
                headers: {
                    'Content-Type': 'text/plain; charset=utf-8',
                },
            })
        }
    } catch (error) {
        console.error('Error in AI SDK chat route:', error)
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
