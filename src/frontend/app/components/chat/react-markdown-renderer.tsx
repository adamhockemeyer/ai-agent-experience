"use client"

import { memo, useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'

interface ReactMarkdownRendererProps {
    content: string
    isStreaming?: boolean
}

// Loading component for HTML visualizations
function HtmlVisualizationLoader() {
    return (
        <div className="w-full h-full min-h-[400px] flex items-center justify-center bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-300 dark:border-gray-600">
            <div className="flex flex-col items-center space-y-3">
                <div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full"></div>
                <div className="text-sm text-gray-600 dark:text-gray-400 font-medium">
                    Loading content...
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-500">
                    Please wait while the HTML content renders
                </div>
            </div>
        </div>
    )
}

// Component for collapsible tool calls
function ToolCallSection({
    summary,
    details,
    type
}: {
    summary: string
    details: string
    type: 'calling' | 'completed'
}) {
    const [isOpen, setIsOpen] = useState(false)

    const bgColor = type === 'calling'
        ? 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800'
        : 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'

    const textColor = type === 'calling'
        ? 'text-blue-700 dark:text-blue-300'
        : 'text-green-700 dark:text-green-300'

    const detailsColor = type === 'calling'
        ? 'text-gray-900 dark:text-gray-100'
        : 'text-gray-900 dark:text-gray-100'

    return (
        <div className={`tool-call ${bgColor} border rounded-md p-2 my-2`}>
            <div
                className={`font-medium ${textColor} cursor-pointer flex items-center text-sm`}
                onClick={() => setIsOpen(!isOpen)}
            >
                <span className={`mr-2 text-xs transition-transform duration-200 ${isOpen ? 'rotate-90' : ''}`}>
                    ▶
                </span>
                {summary}
            </div>
            {isOpen && details && (
                <div className={`text-xs ${detailsColor} mt-2 pl-4`}>
                    <pre className="not-prose whitespace-pre-wrap font-mono bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100 p-2 rounded text-xs border border-gray-300 dark:border-gray-600">
                        {details}
                    </pre>
                </div>
            )}
        </div>
    )
}

// Proper React Markdown implementation with table support
function ProperMarkdownRenderer({ content, isStreaming }: ReactMarkdownRendererProps) {
    // Preprocess content to handle tool calls properly
    const processedContent = content
        // Convert tool call details/summary to a format ReactMarkdown can handle
        .replace(
            /<details>\s*<summary>(🔄 Calling [^<]+)<\/summary>([\s\S]*?)<\/details>/g,
            (match, summary, details) => {
                // Extract JSON from code blocks and store it for the collapsible section
                const jsonMatch = details.match(/```json\n([\s\S]*?)\n```/)
                const jsonContent = jsonMatch ? jsonMatch[1] : details.trim()
                return `\n\n---TOOL_CALL_CALLING---\n${summary}\n${jsonContent}\n---END_TOOL_CALL---\n\n`
            }
        )
        .replace(
            /<details>\s*<summary>(✅ Completed [^<]+)<\/summary>([\s\S]*?)<\/details>/g,
            (match, summary, details) => {
                // Clean up any markdown formatting in details
                const cleanDetails = details.replace(/\*\*(.*?)\*\*/g, '$1').trim()
                return `\n\n---TOOL_CALL_COMPLETED---\n${summary}\n${cleanDetails}\n---END_TOOL_CALL---\n\n`
            }
        )
        .replace(
            /<details>\s*<summary>(❌ Completed [^<]+)<\/summary>([\s\S]*?)<\/details>/g,
            (match, summary, details) => {
                // Clean up any markdown formatting in details
                const cleanDetails = details.replace(/\*\*(.*?)\*\*/g, '$1').trim()
                return `\n\n---TOOL_CALL_ERROR---\n${summary}\n${cleanDetails}\n---END_TOOL_CALL---\n\n`
            }
        )

    return (
        <div className="prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeRaw]}
                components={{
                    // Custom iframe component for safe HTML rendering
                    iframe: ({ src, width, height, title, ...props }: any) => {
                        return (
                            <div className="my-4">
                                <iframe
                                    src={src}
                                    width={width || "100%"}
                                    height={height || "400"}
                                    title={title || "Embedded content"}
                                    className="border border-gray-300 dark:border-gray-600 rounded-lg"
                                    sandbox="allow-scripts allow-same-origin allow-forms"
                                    loading="lazy"
                                    {...props}
                                />
                            </div>
                        )
                    },
                    // Handle tool calls using our custom markers
                    hr: ({ ...props }) => {
                        return <hr className="my-4" {...props} />
                    },
                    // Custom components for regular elements
                    code: ({ inline, className, children, ...props }: any) => {
                        const content = String(children)

                        // Check if this is a tool call JSON block that should be hidden
                        if (!inline && (content.includes('"format": "json"') || content.includes('"api_version"'))) {
                            // Return null to hide standalone JSON blocks that are part of tool calls
                            return null
                        }

                        // Check if this is HTML content that should be rendered
                        if (!inline && className === 'language-html' && content.trim().startsWith('<')) {

                            // Component to handle HTML rendering with loading state
                            function HtmlRenderer() {
                                const [isLoading, setIsLoading] = useState(true)
                                const [htmlUrl, setHtmlUrl] = useState<string>('')
                                const [iframeHeight, setIframeHeight] = useState(400)
                                const [hasError, setHasError] = useState(false)
                                const [isContentReady, setIsContentReady] = useState(false)
                                const iframeRef = useRef<HTMLIFrameElement>(null)
                                const timeoutRef = useRef<NodeJS.Timeout | null>(null)
                                const hasLoadedRef = useRef(false)

                                // Create the HTML blob URL when component mounts
                                useEffect(() => {
                                    // Add unique ID for this specific content
                                    const contentId = `html_${Math.random().toString(36).substr(2, 9)}_${Date.now()}`

                                    // Enhance HTML content
                                    const enhancedContent = `
                                        <!DOCTYPE html>
                                        <html>
                                        <head>
                                            <meta charset="utf-8">
                                            <title>HTML Content</title>
                                            <style>
                                                body { 
                                                    margin: 0; 
                                                    padding: 16px; 
                                                    font-family: system-ui, -apple-system, sans-serif;
                                                    background: white;
                                                }
                                                * { box-sizing: border-box; }
                                            </style>
                                        </head>
                                        <body>
                                            ${content}
                                            <script>
                                                // Signal when content is ready
                                                function signalReady() {
                                                    try {
                                                        const height = Math.max(
                                                            document.body.scrollHeight,
                                                            document.body.offsetHeight,
                                                            document.documentElement.scrollHeight,
                                                            400
                                                        );
                                                        
                                                        window.parent.postMessage({
                                                            type: 'htmlContentReady',
                                                            height: height,
                                                            contentId: '${contentId}'
                                                        }, '*');
                                                    } catch(e) {
                                                        // Silent error handling for postMessage failures
                                                    }
                                                }
                                                
                                                // Signal when fully loaded - give charts time to render
                                                setTimeout(signalReady, 1500);
                                                window.addEventListener('load', signalReady);
                                            </script>
                                        </body>
                                        </html>
                                    `

                                    const htmlBlob = new Blob([enhancedContent], { type: 'text/html' })
                                    const url = URL.createObjectURL(htmlBlob)

                                    // Set the URL and mark content as ready
                                    setHtmlUrl(url)
                                    setIsContentReady(true)

                                    // Simple message handler
                                    const handleMessage = (event: MessageEvent) => {
                                        if (event.data?.type === 'htmlContentReady' && !hasLoadedRef.current) {
                                            hasLoadedRef.current = true

                                            // Set height first
                                            if (event.data.height && event.data.height > 0) {
                                                const adjustedHeight = Math.min(Math.max(event.data.height + 20, 300), 800)
                                                setIframeHeight(adjustedHeight)
                                            }

                                            // Then fade out loading with a smooth delay
                                            setTimeout(() => {
                                                setIsLoading(false)
                                            }, 300)
                                        }
                                    }

                                    window.addEventListener('message', handleMessage)

                                    // Cleanup
                                    return () => {
                                        URL.revokeObjectURL(url)
                                        window.removeEventListener('message', handleMessage)
                                        if (timeoutRef.current) {
                                            clearTimeout(timeoutRef.current)
                                        }
                                    }
                                }, [content])

                                const handleIframeLoad = () => {
                                    // Fallback timeout if PostMessage fails - give charts time to render
                                    timeoutRef.current = setTimeout(() => {
                                        if (!hasLoadedRef.current) {
                                            hasLoadedRef.current = true
                                            // Smooth transition even for fallback
                                            setTimeout(() => {
                                                setIsLoading(false)
                                            }, 300)
                                        }
                                    }, 3000)
                                }

                                const handleIframeError = () => {
                                    hasLoadedRef.current = true
                                    setIsLoading(false)
                                    setHasError(true)
                                }

                                if (hasError) {
                                    return (
                                        <div className="my-4 not-prose">
                                            <div className="border border-red-300 dark:border-red-600 rounded-lg bg-red-50 dark:bg-red-900/20 p-4 text-center">
                                                <p className="text-red-600 dark:text-red-400 text-sm">
                                                    ⚠️ HTML content failed to load. This may happen when multiple embedded contents are rendered simultaneously.
                                                </p>
                                                <details className="mt-2">
                                                    <summary className="cursor-pointer text-xs text-red-500 hover:text-red-600">
                                                        View raw HTML
                                                    </summary>
                                                    <pre className="mt-2 text-xs bg-gray-100 dark:bg-gray-800 p-2 rounded overflow-x-auto text-left">
                                                        {content}
                                                    </pre>
                                                </details>
                                            </div>
                                        </div>
                                    )
                                }

                                return (
                                    <div className="my-4 not-prose relative" style={{ minHeight: iframeHeight }}>
                                        {/* Loading overlay - covers the entire area */}
                                        <div className={`absolute inset-0 z-20 transition-opacity duration-500 ${isLoading ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}>
                                            <HtmlVisualizationLoader />
                                        </div>

                                        {/* Iframe - always rendered when content is ready, initially hidden */}
                                        {isContentReady && htmlUrl && (
                                            <iframe
                                                ref={iframeRef}
                                                src={htmlUrl}
                                                width="100%"
                                                height={iframeHeight}
                                                className={`border border-gray-300 dark:border-gray-600 rounded-lg transition-opacity duration-500 ${isLoading ? 'opacity-0' : 'opacity-100'
                                                    }`}
                                                title={`HTML Content ${Date.now()}`}
                                                sandbox="allow-scripts allow-same-origin"
                                                onLoad={handleIframeLoad}
                                                onError={handleIframeError}
                                                style={{
                                                    overflow: 'hidden',
                                                    scrollbarWidth: 'thin',
                                                    msOverflowStyle: 'none'
                                                }}
                                            />
                                        )}
                                    </div>
                                )
                            }

                            return <HtmlRenderer />
                        }

                        if (inline) {
                            return (
                                <code
                                    className="bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded text-sm font-mono"
                                    {...props}
                                >
                                    {children}
                                </code>
                            )
                        }
                        return (
                            <pre className="not-prose bg-gray-100 dark:bg-gray-800 p-4 rounded-lg overflow-x-auto my-4">
                                <code className="text-sm font-mono" {...props}>
                                    {children}
                                </code>
                            </pre>
                        )
                    },
                    // Stable paragraph rendering
                    p: ({ children, ...props }) => {
                        const text = String(children)

                        // Handle tool call markers
                        if (text.includes('---TOOL_CALL_CALLING---')) {
                            const lines = text.split('\n')
                            const summary = lines.find(line => line.includes('🔄 Calling'))
                            const details = lines.filter(line =>
                                !line.includes('---TOOL_CALL_CALLING---') &&
                                !line.includes('---END_TOOL_CALL---') &&
                                !line.includes('🔄 Calling') &&
                                line.trim()
                            ).join('\n').trim()

                            return <ToolCallSection summary={summary || ''} details={details} type="calling" />
                        }

                        if (text.includes('---TOOL_CALL_COMPLETED---')) {
                            const lines = text.split('\n')
                            const summary = lines.find(line => line.includes('✅ Completed'))
                            const details = lines.filter(line =>
                                !line.includes('---TOOL_CALL_COMPLETED---') &&
                                !line.includes('---END_TOOL_CALL---') &&
                                !line.includes('✅ Completed') &&
                                line.trim()
                            ).join('\n').trim()

                            return <ToolCallSection summary={summary || ''} details={details} type="completed" />
                        }

                        if (text.includes('---TOOL_CALL_ERROR---')) {
                            const lines = text.split('\n')
                            const summary = lines.find(line => line.includes('❌ Completed'))
                            const details = lines.filter(line =>
                                !line.includes('---TOOL_CALL_ERROR---') &&
                                !line.includes('---END_TOOL_CALL---') &&
                                !line.includes('❌ Completed') &&
                                line.trim()
                            ).join('\n').trim()

                            return <ToolCallSection summary={summary || ''} details={details} type="completed" />
                        }

                        // Skip rendering paragraphs that are just tool call markers
                        if (text.includes('---TOOL_CALL_') || text.includes('---END_TOOL_CALL---')) {
                            return null
                        }

                        return (
                            <p className="mb-4" {...props}>
                                {children}
                            </p>
                        )
                    },
                    // Table styling for better appearance
                    table: ({ children, ...props }) => (
                        <div className="overflow-x-auto my-4">
                            <table className="min-w-full border-collapse border border-gray-300 dark:border-gray-600" {...props}>
                                {children}
                            </table>
                        </div>
                    ),
                    th: ({ children, ...props }) => (
                        <th className="border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-800 px-3 py-2 text-left font-semibold" {...props}>
                            {children}
                        </th>
                    ),
                    td: ({ children, ...props }) => (
                        <td className="border border-gray-300 dark:border-gray-600 px-3 py-2" {...props}>
                            {children}
                        </td>
                    )
                }}
            >
                {processedContent}
            </ReactMarkdown>
        </div>
    )
}

// Memoize to prevent unnecessary re-renders when content hasn't changed
const ReactMarkdownRenderer = memo(ProperMarkdownRenderer)

export default ReactMarkdownRenderer
