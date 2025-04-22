"use client"

import type React from "react"

import { useState, useRef, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea-fixed"
import { ScrollArea } from "@/components/ui/scroll-area"
import { PaperclipIcon, SendIcon, Trash2, Copy, Check } from "lucide-react"
import type { Agent, ChatMessage, Attachment, ChatResponse } from "@/lib/types"
import { sendMessage } from "@/app/actions/agent-actions"
import ChatMessageItem from "./chat-message-item"
import { v4 as uuidv4 } from "uuid"
import { Bot, ThumbsUp, ThumbsDown, Bug, Code, FileText, Zap, Lightbulb } from "lucide-react"
import BotTypingIndicator from "./bot-typing-indicator"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import MarkdownRenderer from "./markdown-renderer"

interface ChatInterfaceProps {
  agent: Agent
}

export default function ChatInterface({ agent }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [attachments, setAttachments] = useState<Attachment[]>([])
  const [streamedResponses, setStreamedResponses] = useState<ChatResponse[]>([])
  const [currentTraceId, setCurrentTraceId] = useState<string | undefined>(undefined)
  const [currentSessionId, setCurrentSessionId] = useState<string | undefined>(undefined)
  const [isDebugDialogOpen, setIsDebugDialogOpen] = useState(false)
  const [isCopied, setIsCopied] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, streamedResponses])

  // Reset attachments when switching agents
  useEffect(() => {
    setAttachments([])
    setInput("")
    setMessages([])
    setStreamedResponses([])
    setCurrentTraceId(undefined)
    setCurrentSessionId(uuidv4()) // Generate a new session ID when switching agents
  }, [agent.id])

  const copyTraceId = () => {
    if (currentTraceId) {
      navigator.clipboard.writeText(currentTraceId)
      setIsCopied(true)
      setTimeout(() => setIsCopied(false), 2000)
    }
  }

  const handleSendMessage = async () => {
    if (!input.trim() && attachments.length === 0) return

    // If there are streamed responses, add them as a bot message to the chat history
    if (streamedResponses.length > 0) {
      // Combine all streamed responses into a single message
      const combinedContent = streamedResponses
        .map((response) => response.content)
        .join("\n")
        .trim()

      // Add the bot's response to the message history
      const botMessage: ChatMessage = {
        id: uuidv4(),
        role: "assistant",
        content: combinedContent,
        timestamp: Date.now(),
        traceId: currentTraceId,
      }

      setMessages((prev) => [...prev, botMessage])

      // Clear streamed responses after adding to message history
      setStreamedResponses([])
    }

    const newMessage: ChatMessage = {
      id: uuidv4(),
      role: "user",
      content: input,
      timestamp: Date.now(),
      attachments: attachments.length > 0 ? [...attachments] : undefined,
    }

    setMessages((prev) => [...prev, newMessage])
    setInput("")
    setAttachments([])
    setIsLoading(true)
    setCurrentTraceId(undefined)

    // Don't reset the session ID for follow-up questions
    // If no session ID exists yet, create one
    if (!currentSessionId) {
      setCurrentSessionId(uuidv4())
    }

    try {
      // Use the existing session ID or create a new one if it doesn't exist
      const sessionId = currentSessionId || uuidv4()

      const { stream, traceId } = await sendMessage(agent.id, input, attachments, sessionId)

      if (traceId) {
        setCurrentTraceId(traceId)
      }

      // If this is the first message, save the session ID
      if (!currentSessionId) {
        setCurrentSessionId(sessionId)
      }

      // Create a response ID for the streaming content
      const responseId = uuidv4()

      // Initialize with empty content
      setStreamedResponses([
        {
          id: responseId,
          content: "",
          contentType: "text",
        },
      ])

      const reader = stream.getReader()
      const decoder = new TextDecoder()

      let done = false
      while (!done) {
        const { value, done: doneReading } = await reader.read()
        done = doneReading

        if (value) {
          // Decode the chunk
          const text = decoder.decode(value, { stream: true })

          // Update the streamed response by appending the new text
          setStreamedResponses((prev) => {
            // Get the current response (should be only one)
            const currentResponse = prev[0]

            // Create a new response with the appended text
            const updatedResponse = {
              ...currentResponse,
              content: currentResponse.content + text,
            }

            // Return the updated array
            return [updatedResponse]
          })
        }
      }
    } catch (error) {
      console.error("Error sending message:", error)
      setStreamedResponses([
        {
          id: uuidv4(),
          content: "An error occurred while processing your request.",
          contentType: "error",
        },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const newAttachments: Attachment[] = Array.from(e.target.files).map((file) => ({
        id: uuidv4(),
        name: file.name,
        type: file.type,
        url: URL.createObjectURL(file),
      }))

      setAttachments((prev) => [...prev, ...newAttachments])
    }
  }

  const handleRemoveAttachment = (id: string) => {
    setAttachments((prev) => prev.filter((attachment) => attachment.id !== id))
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  const handleSamplePromptClick = (prompt: string) => {
    setInput(prompt)
  }

  const handleDebugClick = () => {
    setIsDebugDialogOpen(true)
  }

  // Check if chat is empty (no user messages yet)
  const isChatEmpty = messages.length === 0

  return (
    <div className="flex flex-col h-full">
      {/* Chat messages */}
      <ScrollArea className="flex-1 p-4">
        <div className="space-y-4">
          {/* Welcome message when chat is empty */}
          {isChatEmpty && (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center mb-6">
                <Bot className="h-10 w-10 text-primary" />
              </div>
              <h2 className="text-2xl font-bold mb-2">{agent.name}</h2>
              <p className="text-muted-foreground max-w-md mb-6">
                {agent.description || agent.systemPrompt.split(".")[0] + "."}
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-md mx-auto">
                {/* Model info */}
                <div className="bg-secondary/30 rounded-lg p-4 flex flex-col items-center text-center">
                  <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center mb-2">
                    <Bot className="h-5 w-5 text-primary" />
                  </div>
                  <h3 className="font-medium mb-1">Powered by</h3>
                  <p className="text-sm text-muted-foreground">
                    {agent.modelSelection.provider}: {agent.modelSelection.model}
                  </p>
                </div>

                {/* Capabilities */}
                <div className="bg-secondary/30 rounded-lg p-4 flex flex-col items-center text-center">
                  <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center mb-2">
                    <Zap className="h-5 w-5 text-primary" />
                  </div>
                  <h3 className="font-medium mb-1">Capabilities</h3>
                  <div className="flex flex-wrap justify-center gap-1 text-xs">
                    {agent.codeInterpreter && (
                      <span className="bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300 px-2 py-1 rounded-full flex items-center">
                        <Code className="h-3 w-3 mr-1" /> Code
                      </span>
                    )}
                    {agent.fileUpload && (
                      <span className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300 px-2 py-1 rounded-full flex items-center">
                        <FileText className="h-3 w-3 mr-1" /> Files
                      </span>
                    )}
                    {agent.tools.length > 0 && (
                      <span className="bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300 px-2 py-1 rounded-full flex items-center">
                        <Zap className="h-3 w-3 mr-1" /> Tools: {agent.tools.length}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {messages.map((message) => (
            <ChatMessageItem key={message.id} message={message} />
          ))}

          {/* Bot response area */}
          {(isLoading || streamedResponses.length > 0) && (
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center text-primary-foreground">
                <Bot className="h-5 w-5" />
              </div>
              <div className="flex-1 bg-muted p-3 rounded-lg">
                {streamedResponses.map((response) => (
                  <div key={response.id}>
                    {response.contentType === "text" && (
                      <div className="markdown-content prose prose-sm dark:prose-invert max-w-none">
                        <MarkdownRenderer content={response.content} />
                      </div>
                    )}
                    {response.contentType === "code" && (
                      <div className="my-2 bg-background rounded-md p-3 overflow-x-auto">
                        <pre>
                          <code className={response.language ? `language-${response.language}` : ""}>
                            {response.content}
                          </code>
                        </pre>
                      </div>
                    )}
                    {response.contentType === "image" && (
                      <div className="my-2">
                        <img
                          src={response.url || response.content}
                          alt="Generated content"
                          className="max-w-full rounded-md"
                        />
                      </div>
                    )}
                    {response.contentType === "iframe" && (
                      <div className="my-2" dangerouslySetInnerHTML={{ __html: response.content }} />
                    )}
                    {response.contentType === "error" && <p className="text-destructive">{response.content}</p>}
                  </div>
                ))}

                {isLoading && <BotTypingIndicator />}

                {!isLoading && streamedResponses.length > 0 && (
                  <div className="flex items-center justify-end gap-2 mt-2">
                    <Button variant="ghost" size="sm">
                      <ThumbsUp className="h-4 w-4 mr-1" />
                      Helpful
                    </Button>
                    <Button variant="ghost" size="sm">
                      <ThumbsDown className="h-4 w-4 mr-1" />
                      Not Helpful
                    </Button>
                    <Button variant="ghost" size="sm" onClick={handleDebugClick}>
                      <Bug className="h-4 w-4 mr-1" />
                      Debug
                    </Button>
                    <Button variant="ghost" size="sm">
                      <Copy className="h-4 w-4 mr-1" />
                      Copy
                    </Button>
                  </div>
                )}
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </ScrollArea>

      {/* Sample prompts - show when there are no user messages or only one user message */}
      {messages.filter((m) => m.role === "user").length < 2 && (
        <div className="px-4 py-2 border-t">
          {agent.defaultPrompts && agent.defaultPrompts.length > 0 ? (
            <>
              <p className="text-sm font-medium mb-2">Try asking:</p>
              {/* Filter out any empty prompts before rendering */}
              {agent.defaultPrompts.filter((prompt) => prompt.trim().length > 0).length > 0 ? (
                <div className="flex flex-wrap gap-2 w-full">
                  {agent.defaultPrompts
                    .filter((prompt) => prompt.trim().length > 0)
                    .map((prompt, index) => (
                      <Button
                        key={index}
                        variant="outline"
                        size="sm"
                        onClick={() => handleSamplePromptClick(prompt)}
                        title={prompt}
                        className="max-w-full overflow-hidden"
                      >
                        <span className="truncate block w-full text-left">{prompt}</span>
                      </Button>
                    ))}
                </div>
              ) : (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10">
                    <Lightbulb className="h-3.5 w-3.5 text-primary" />
                  </div>
                  <p>Add example prompts in agent settings.</p>
                </div>
              )}
            </>
          ) : (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10">
                <Lightbulb className="h-3.5 w-3.5 text-primary" />
              </div>
              <p>Add example prompts in agent settings to show quick suggestions here.</p>
            </div>
          )}
        </div>
      )}

      {/* Attachments */}
      {attachments.length > 0 && (
        <div className="px-4 py-2 border-t">
          <div className="flex flex-wrap gap-2">
            {attachments.map((attachment) => (
              <div key={attachment.id} className="flex items-center gap-2 bg-muted p-2 rounded-md">
                <span className="text-sm truncate max-w-[150px]">{attachment.name}</span>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-5 w-5"
                  onClick={() => handleRemoveAttachment(attachment.id)}
                >
                  <Trash2 className="h-3 w-3" />
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Input area */}
      <div className="p-4 border-t">
        <div className="relative">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your message..."
            className="min-h-[60px] resize-none pr-20"
            disabled={isLoading}
          />
          <div className="absolute right-2 bottom-2 flex items-center gap-2">
            {agent.fileUpload && (
              <>
                <input type="file" ref={fileInputRef} onChange={handleFileUpload} className="hidden" multiple />
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isLoading}
                >
                  <PaperclipIcon className="h-4 w-4" />
                </Button>
              </>
            )}
            <Button
              variant="default"
              size="icon"
              className="h-8 w-8 bg-primary hover:bg-primary/90"
              onClick={handleSendMessage}
              disabled={isLoading || (!input.trim() && attachments.length === 0)}
            >
              <SendIcon className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>

      {/* Debug Dialog */}
      <Dialog open={isDebugDialogOpen} onOpenChange={setIsDebugDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Debug Information</DialogTitle>
            <DialogDescription>Technical details for troubleshooting.</DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {currentTraceId ? (
              <div className="bg-muted p-4 rounded-md">
                <div className="text-sm font-medium mb-1">OpenTelemetry Trace ID:</div>
                <div className="flex items-center">
                  <div className="font-mono text-xs bg-background p-2 rounded border overflow-x-auto flex-1">
                    {currentTraceId}
                  </div>
                  <Button variant="ghost" size="sm" className="ml-2" onClick={copyTraceId}>
                    {isCopied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="text-muted-foreground text-sm">No trace ID available for this response.</div>
            )}

            <div className="bg-muted p-4 rounded-md">
              <div className="text-sm font-medium mb-1">Agent Information:</div>
              <div className="text-xs">
                <div>
                  <span className="font-medium">ID:</span> {agent.id}
                </div>
                <div>
                  <span className="font-medium">Type:</span> {agent.agentType}
                </div>
                <div>
                  <span className="font-medium">Model:</span> {agent.modelSelection.provider} /{" "}
                  {agent.modelSelection.model}
                </div>
                {currentSessionId && (
                  <div>
                    <span className="font-medium">Session ID:</span> {currentSessionId}
                  </div>
                )}
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button onClick={() => setIsDebugDialogOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
