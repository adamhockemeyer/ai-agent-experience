"use client"

import { useCompletion } from '@ai-sdk/react'
import { useState, useRef, useEffect, useCallback, useMemo, memo } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { Send, StopCircle, Paperclip, X } from 'lucide-react'
import { Agent, Attachment } from '@/lib/types'
import ReactMarkdownRenderer from './react-markdown-renderer'
import ChatFeedback from './chat-feedback'

interface AiSdkChatInterfaceOptimizedProps {
    agent: Agent
}

// Memoized chat message component to prevent unnecessary re-renders
const ChatMessage = memo(function ChatMessage({
    message
}: {
    message: { id: string, type: 'user' | 'assistant', content: string, attachments?: Attachment[], traceId?: string }
}) {
    return (
        <div className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[75%] rounded-lg px-3 py-2 ${message.type === 'user'
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted'
                }`}>
                {message.type === 'user' ? (
                    <div>
                        <p className="text-sm">{message.content}</p>
                        {message.attachments && message.attachments.length > 0 && (
                            <div className="mt-2 space-y-1">
                                {message.attachments.map((attachment) => (
                                    <div key={attachment.id} className="text-xs opacity-75 flex items-center gap-1">
                                        <Paperclip className="h-3 w-3" />
                                        {attachment.name}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="space-y-3">
                        <ReactMarkdownRenderer content={message.content} />
                        {/* Feedback controls inside the bot response area */}
                        <div className="pt-2 border-t border-border/20">
                            <ChatFeedback messageId={message.id} traceId={message.traceId} />
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
})

// Memoized attachment component
const AttachmentItem = memo(function AttachmentItem({
    attachment,
    onRemove
}: {
    attachment: Attachment,
    onRemove: (id: string) => void
}) {
    const handleRemove = useCallback(() => {
        onRemove(attachment.id)
    }, [attachment.id, onRemove])

    return (
        <div className="flex items-center gap-2 bg-muted rounded-lg px-3 py-2 text-sm">
            <Paperclip className="h-4 w-4" />
            <span className="truncate max-w-[150px]">{attachment.name}</span>
            <button
                onClick={handleRemove}
                className="text-muted-foreground hover:text-foreground"
            >
                <X className="h-4 w-4" />
            </button>
        </div>
    )
})

// Enhanced loading indicator component with different states
const ThinkingIndicator = memo(function ThinkingIndicator({
    hasContent,
    isLoading
}: {
    hasContent: boolean,
    isLoading: boolean
}) {
    if (!isLoading) return null

    const showStreamingIndicator = hasContent && isLoading

    return (
        <div className="flex justify-center py-4">
            <div className="flex items-center space-x-3 px-4 py-3 bg-muted/50 rounded-full border border-border/20">
                {showStreamingIndicator ? (
                    <>
                        <div className="flex space-x-1">
                            <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                            <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                            <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                        </div>
                        <span className="text-sm text-muted-foreground font-medium">Streaming response...</span>
                    </>
                ) : (
                    <>
                        <div className="animate-spin h-5 w-5 border-2 border-blue-500 border-t-transparent rounded-full"></div>
                        <span className="text-sm text-muted-foreground font-medium">
                            Thinking...
                        </span>
                    </>
                )}
            </div>
        </div>
    )
})

// Memoized sample prompt button
const SamplePromptButton = memo(function SamplePromptButton({
    prompt,
    onClick,
    disabled
}: {
    prompt: string,
    onClick: (prompt: string) => void,
    disabled: boolean
}) {
    const handleClick = useCallback(() => {
        onClick(prompt)
    }, [prompt, onClick])

    const truncatedPrompt = useMemo(() =>
        prompt.length > 50 ? `${prompt.substring(0, 50)}...` : prompt
        , [prompt])

    return (
        <button
            onClick={handleClick}
            className="text-xs px-3 py-1.5 rounded-full border hover:bg-muted/50 transition-colors bg-background text-muted-foreground hover:text-foreground"
            disabled={disabled}
        >
            {truncatedPrompt}
        </button>
    )
})

// Memoized welcome screen sample prompts
const WelcomeScreenPrompts = memo(function WelcomeScreenPrompts({
    prompts,
    onPromptClick,
    disabled
}: {
    prompts: string[],
    onPromptClick: (prompt: string) => void,
    disabled: boolean
}) {
    return (
        <div className="w-full max-w-lg space-y-4">
            <h3 className="text-lg font-medium">Try asking:</h3>
            <div className="space-y-3">
                {prompts.slice(0, 3).map((prompt, index) => (
                    <button
                        key={index}
                        onClick={() => onPromptClick(prompt)}
                        className="w-full text-left p-4 text-sm rounded-lg border hover:bg-muted/50 transition-colors bg-background"
                        disabled={disabled}
                    >
                        {prompt}
                    </button>
                ))}
            </div>
        </div>
    )
})

export default function AiSdkChatInterfaceOptimized({ agent }: AiSdkChatInterfaceOptimizedProps) {
    const [input, setInput] = useState("")
    const [attachments, setAttachments] = useState<Attachment[]>([])
    const [sessionId, setSessionId] = useState<string>(() => crypto.randomUUID())
    const [fileError, setFileError] = useState<string | null>(null)
    const [chatHistory, setChatHistory] = useState<Array<{ id: string, type: 'user' | 'assistant', content: string, attachments?: Attachment[], traceId?: string }>>([])
    const [currentTraceId, setCurrentTraceId] = useState<string | undefined>(undefined)
    const currentTraceIdRef = useRef<string | undefined>(undefined)
    const messagesEndRef = useRef<HTMLDivElement>(null)
    const fileInputRef = useRef<HTMLInputElement>(null)

    // Memoize file type configurations to prevent recreation
    const fileConfig = useMemo(() => ({
        ALLOWED_FILE_TYPES: [
            // Images
            "image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml",
            // Documents
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            // Text files
            "text/plain",
            "text/csv",
            "text/html",
            "text/markdown",
            "application/json",
            "application/xml",
        ],
        MAX_FILE_SIZE_MB: 10,
        MAX_FILE_SIZE_BYTES: 10 * 1024 * 1024
    }), [])

    // Custom fetch function to capture trace ID from response headers
    const customFetch = useCallback(async (input: RequestInfo | URL, init?: RequestInit) => {
        const response = await fetch(input, init)

        // Capture trace ID from response headers
        const traceId = response.headers.get('X-OTel-Trace-ID')

        if (traceId) {
            setCurrentTraceId(traceId)
            currentTraceIdRef.current = traceId
            console.log('Captured trace ID:', traceId)
        }

        return response
    }, [])

    // AI SDK useCompletion hook configuration
    const {
        completion,
        input: completionInput,
        handleInputChange,
        handleSubmit: originalHandleSubmit,
        isLoading,
        stop,
        error,
        setInput: setCompletionInput,
    } = useCompletion({
        api: '/api/completion',
        streamProtocol: 'text',
        body: {
            agent_id: agent.id,
            session_id: sessionId,
            attachments,
        },
        headers: {
            'Content-Type': 'application/json',
            'X-Agent-ID': agent.id,
        },
        fetch: customFetch,
        onFinish: (prompt: string, completion: string) => {
            console.log('AI SDK - Completion finished:', { prompt, completion })

            const traceIdToUse = currentTraceIdRef.current || currentTraceId

            setChatHistory(prev => [
                ...prev,
                {
                    id: crypto.randomUUID(),
                    type: 'assistant',
                    content: completion,
                    traceId: traceIdToUse
                }
            ])

            // Clear input and attachments after completion
            setTimeout(() => {
                setCompletionInput("")
                setAttachments([])
            }, 0)
        },
        onError: (error: Error) => {
            console.error('AI SDK - Error:', error)
        },
    })

    // Memoize computed values
    const isChatEmpty = useMemo(() => !completion && chatHistory.length === 0, [completion, chatHistory])

    // Memoized callback functions to prevent unnecessary re-renders
    const handleSubmit = useCallback((e?: React.FormEvent) => {
        if (e) e.preventDefault()
        if (!completionInput.trim() || isLoading) return

        setChatHistory(prev => [
            ...prev,
            {
                id: crypto.randomUUID(),
                type: 'user',
                content: completionInput,
                attachments: attachments.length > 0 ? [...attachments] : undefined
            }
        ])

        originalHandleSubmit(e)
        setCompletionInput("")
        setAttachments([])
    }, [completionInput, isLoading, attachments, originalHandleSubmit, setCompletionInput])

    const handleSamplePromptClick = useCallback((prompt: string) => {
        setCompletionInput(prompt)
    }, [setCompletionInput])

    const validateFile = useCallback((file: File): { valid: boolean; error?: string } => {
        const fileName = file.name.toLowerCase()
        const isMarkdownFile = fileName.endsWith('.md') || fileName.endsWith('.markdown')

        if (!fileConfig.ALLOWED_FILE_TYPES.includes(file.type) && !isMarkdownFile) {
            return {
                valid: false,
                error: `File type "${file.type || 'unknown'}" is not supported. Please upload an image, document, or text file.`
            }
        }

        if (file.size > fileConfig.MAX_FILE_SIZE_BYTES) {
            return {
                valid: false,
                error: `File size (${(file.size / (1024 * 1024)).toFixed(1)}MB) exceeds the maximum allowed size of ${fileConfig.MAX_FILE_SIZE_MB}MB.`
            }
        }

        return { valid: true }
    }, [fileConfig])

    const handleFileUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        const files = Array.from(e.target.files || [])
        setFileError(null)

        files.forEach(file => {
            const validation = validateFile(file)

            if (!validation.valid) {
                setFileError(validation.error!)
                return
            }

            // Use FileReader to convert file to base64 data URL
            const reader = new FileReader()
            reader.onload = (event) => {
                const base64Data = event.target?.result as string
                const newAttachment: Attachment = {
                    id: crypto.randomUUID(),
                    name: file.name,
                    type: file.type || 'application/octet-stream',
                    url: base64Data, // This will be in the format "data:image/jpeg;base64,..."
                }

                setAttachments(prev => [...prev, newAttachment])
            }

            // Read the file as a data URL (base64)
            reader.readAsDataURL(file)
        })

        if (fileInputRef.current) {
            fileInputRef.current.value = ''
        }
    }, [validateFile])

    const handleRemoveAttachment = useCallback((id: string) => {
        setAttachments(prev => prev.filter(att => att.id !== id))
    }, [])

    const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSubmit(e as any)
        }
    }, [handleSubmit])

    const handleFileInputClick = useCallback(() => {
        fileInputRef.current?.click()
    }, [])

    // Sync input state with completion input (optimized)
    useEffect(() => {
        setInput(completionInput)
    }, [completionInput])

    // Optimized scroll to bottom with debouncing
    useEffect(() => {
        const timeoutId = setTimeout(() => {
            messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
        }, 50) // Small delay to prevent excessive scrolling during streaming

        return () => clearTimeout(timeoutId)
    }, [completion, chatHistory])

    // Reset state when agent changes
    useEffect(() => {
        setChatHistory([])
        setAttachments([])
        setCompletionInput("")
        setFileError(null)
        setCurrentTraceId(undefined)
        currentTraceIdRef.current = undefined
    }, [agent.id, setCompletionInput])

    // Memoized sample prompts section for bottom input area
    const bottomSamplePrompts = useMemo(() => {
        if (!agent.defaultPrompts || agent.defaultPrompts.length === 0 || isChatEmpty) {
            return null
        }

        return (
            <div className="px-4 pt-4">
                <div className="flex flex-wrap gap-2">
                    {agent.defaultPrompts.slice(0, 3).map((prompt, index) => (
                        <SamplePromptButton
                            key={index}
                            prompt={prompt}
                            onClick={handleSamplePromptClick}
                            disabled={isLoading}
                        />
                    ))}
                </div>
            </div>
        )
    }, [agent.defaultPrompts, isChatEmpty, isLoading, handleSamplePromptClick])

    // Memoized welcome screen prompts
    const welcomeScreenPrompts = useMemo(() => {
        if (!agent.defaultPrompts || agent.defaultPrompts.length === 0) {
            return null
        }

        return (
            <WelcomeScreenPrompts
                prompts={agent.defaultPrompts}
                onPromptClick={handleSamplePromptClick}
                disabled={isLoading}
            />
        )
    }, [agent.defaultPrompts, handleSamplePromptClick, isLoading])

    return (
        <div className="flex h-full flex-col">
            {/* Messages Container */}
            <div className="flex-1 overflow-auto p-4 space-y-4">
                {/* Show centered welcome screen when chat is empty */}
                {isChatEmpty && (
                    <div className="flex flex-col items-center justify-center h-full max-w-2xl mx-auto text-center space-y-8">
                        {/* Agent Icon */}
                        <div className="w-20 h-20 bg-blue-100 dark:bg-blue-900/20 rounded-full flex items-center justify-center">
                            <span className="text-blue-600 dark:text-blue-400 text-2xl">🤖</span>
                        </div>

                        {/* Agent Info */}
                        <div className="space-y-2">
                            <h1 className="text-2xl font-bold">{agent.name}</h1>
                            <p className="text-muted-foreground">{agent.description}</p>
                        </div>

                        {/* Powered By & Capabilities */}
                        <div className="flex gap-8 justify-center">
                            <div className="text-center">
                                <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/20 rounded-full flex items-center justify-center mx-auto mb-2">
                                    <span className="text-blue-600 text-xl">⚡</span>
                                </div>
                                <h3 className="font-medium mb-1">Powered by</h3>
                                <p className="text-sm text-muted-foreground">AzureOpenAI: gpt-4.1</p>
                            </div>
                            <div className="text-center">
                                <div className="w-12 h-12 bg-yellow-100 dark:bg-yellow-900/20 rounded-full flex items-center justify-center mx-auto mb-2">
                                    <span className="text-yellow-600 text-xl">🛠️</span>
                                </div>
                                <h3 className="font-medium mb-1">Capabilities</h3>
                                <p className="text-sm text-muted-foreground">🔧 Tools: 1</p>
                            </div>
                        </div>

                        {/* Memoized Welcome Screen Sample Prompts */}
                        {welcomeScreenPrompts}
                    </div>
                )}

                {/* Optimized chat history rendering */}
                {chatHistory.map((message) => (
                    <ChatMessage key={message.id} message={message} />
                ))}

                {/* Show the current AI completion in progress */}
                {completion && isLoading && (
                    <div className="flex justify-start">
                        <div
                            className="rounded-lg bg-muted px-3 py-2"
                            style={{
                                // Set stable width during streaming to prevent container size changes
                                width: "75%",
                                maxWidth: "75%",
                                minWidth: "300px", // Ensure minimum readable width
                                // Prevent the container itself from changing size
                                boxSizing: "border-box"
                            }}
                        >
                            <div className="space-y-3">
                                <div
                                    className="streaming-content-container"
                                    style={{
                                        // Simple, stable container
                                        minHeight: "1.2em",
                                        wordBreak: "break-word"
                                    }}
                                >
                                    <ReactMarkdownRenderer content={completion} isStreaming={true} />
                                </div>
                                {/* Feedback controls inside the streaming response area */}
                                <div className="pt-2 border-t border-border/20">
                                    <ChatFeedback messageId={`streaming-${sessionId}`} traceId={currentTraceId} />
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* Enhanced thinking/streaming indicator */}
                <ThinkingIndicator hasContent={!!completion} isLoading={isLoading} />

                {/* Show error if any */}
                {error && (
                    <div className="flex justify-start">
                        <div
                            className="rounded-lg bg-red-100 dark:bg-red-900/20 border border-red-200 dark:border-red-800 px-3 py-2"
                            style={{
                                width: "75%",
                                maxWidth: "75%",
                                minWidth: "300px",
                                boxSizing: "border-box"
                            }}
                        >
                            <p className="text-sm text-red-800 dark:text-red-200">Error: {error.message}</p>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="border-t bg-background space-y-3">
                {/* Memoized Sample Questions - Always visible above input */}
                {bottomSamplePrompts}

                <div className="p-4">
                    {/* File Error Display */}
                    {fileError && (
                        <div className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md p-2 mb-3">
                            {fileError}
                        </div>
                    )}

                    {/* Optimized Attachments Display */}
                    {attachments.length > 0 && (
                        <div className="flex flex-wrap gap-2 mb-3">
                            {attachments.map((attachment) => (
                                <AttachmentItem
                                    key={attachment.id}
                                    attachment={attachment}
                                    onRemove={handleRemoveAttachment}
                                />
                            ))}
                        </div>
                    )}

                    {/* Input Form */}
                    <form onSubmit={handleSubmit} className="space-y-3">
                        <div className="flex gap-2">
                            <div className="flex-1 relative">
                                <Textarea
                                    value={completionInput}
                                    onChange={handleInputChange}
                                    onKeyDown={handleKeyDown}
                                    placeholder={`Message ${agent.name}...`}
                                    className="min-h-[50px] max-h-[200px] resize-none pr-12"
                                    disabled={isLoading}
                                />

                                {/* File Upload Button */}
                                <button
                                    type="button"
                                    onClick={handleFileInputClick}
                                    className="absolute right-3 top-3 text-muted-foreground hover:text-foreground disabled:opacity-50"
                                    disabled={isLoading}
                                >
                                    <Paperclip className="h-4 w-4" />
                                </button>

                                <input
                                    ref={fileInputRef}
                                    type="file"
                                    multiple
                                    onChange={handleFileUpload}
                                    className="hidden"
                                    accept={fileConfig.ALLOWED_FILE_TYPES.join(",")}
                                />
                            </div>

                            {/* Send/Stop Button */}
                            {isLoading ? (
                                <Button
                                    type="button"
                                    onClick={stop}
                                    size="sm"
                                    variant="outline"
                                    className="self-end"
                                >
                                    <StopCircle className="h-4 w-4" />
                                </Button>
                            ) : (
                                <Button
                                    type="submit"
                                    size="sm"
                                    className="self-end"
                                    disabled={!completionInput.trim() || isLoading}
                                >
                                    <Send className="h-4 w-4" />
                                </Button>
                            )}
                        </div>
                    </form>
                </div>
            </div>
        </div>
    )
}
