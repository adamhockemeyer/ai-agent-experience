"use client"

import { useState, useEffect } from "react"
import { Bot, Check, ArrowUp, Code, FileText, Database } from "lucide-react"

// Define the structure for our conversation examples
interface Message {
  role: "user" | "assistant"
  content: string
  type?: "code" | "text" | "thinking" | "api-call"
  apiCallType?: string
}

interface ConversationExample {
  title: string
  messages: Message[]
}

// Define several conversation examples to cycle through
const conversationExamples: ConversationExample[] = [
  {
    title: "Weather Query",
    messages: [
      { role: "user", content: "How does the weather look for tomorrow?" },
      { role: "assistant", content: "Fetching weather data...", type: "api-call", apiCallType: "weather" },
      { role: "assistant", content: "Tomorrow will be sunny with a high of 72°F. Perfect for outdoor activities!" },
    ],
  },
  {
    title: "Code Generation",
    messages: [
      { role: "user", content: "Write a function to calculate fibonacci numbers" },
      {
        role: "assistant",
        content: "function fibonacci(n) {\n  if (n <= 1) return n;\n  return fibonacci(n-1) + fibonacci(n-2);\n}",
        type: "code",
      },
    ],
  },
  {
    title: "Data Analysis",
    messages: [
      { role: "user", content: "Can you analyze my sales data for trends?" },
      { role: "assistant", content: "Analyzing sales data...", type: "api-call", apiCallType: "database" },
      {
        role: "assistant",
        content:
          "I've analyzed your sales data and found a 15% increase in Q4 compared to Q3. Your top-performing product was the premium subscription package.",
      },
    ],
  },
  {
    title: "Document Processing",
    messages: [
      { role: "user", content: "Summarize this PDF report for me" },
      { role: "assistant", content: "Processing document...", type: "api-call", apiCallType: "document" },
      {
        role: "assistant",
        content:
          "The report highlights three key findings: 1) Market share increased by 7%, 2) Customer satisfaction improved to 94%, and 3) New product line exceeded revenue targets by 20%.",
      },
    ],
  },
]

export default function HeroChatShowcase() {
  const [currentExampleIndex, setCurrentExampleIndex] = useState(0)
  const [visibleMessages, setVisibleMessages] = useState<Message[]>([])
  const [isTyping, setIsTyping] = useState(false)
  const [typingText, setTypingText] = useState("")
  const [typingIndex, setTypingIndex] = useState(0)
  const [messageIndex, setMessageIndex] = useState(0)

  // Reset and start a new conversation example
  const startNewExample = (index: number) => {
    // Fade out
    const container = document.querySelector(".chat-container") as HTMLElement
    if (container) {
      container.style.opacity = "0"
    }

    // Wait for fade out, then reset state
    setTimeout(() => {
      setVisibleMessages([])
      setTypingText("")
      setTypingIndex(0)
      setMessageIndex(0)
      setCurrentExampleIndex(index)

      // Fade back in
      setTimeout(() => {
        if (container) {
          container.style.opacity = "1"
        }
      }, 50)
    }, 500)
  }

  useEffect(() => {
    // Cycle to the next example after completing the current one
    const cycleTimer = setTimeout(() => {
      const nextIndex = (currentExampleIndex + 1) % conversationExamples.length
      startNewExample(nextIndex)
    }, 12000) // Change example every 12 seconds

    return () => clearTimeout(cycleTimer)
  }, [currentExampleIndex])

  useEffect(() => {
    const currentExample = conversationExamples[currentExampleIndex]

    // If we've shown all messages in this example, do nothing
    if (messageIndex >= currentExample.messages.length) return

    const currentMessage = currentExample.messages[messageIndex]

    // Handle different message types
    if (currentMessage.role === "user") {
      // Show user message immediately
      setVisibleMessages((prev) => [...prev, currentMessage])
      setMessageIndex((prev) => prev + 1)

      // Add a small delay before showing the next message
      setTimeout(() => {
        setMessageIndex((prev) => prev)
      }, 1000)
    } else if (currentMessage.type === "api-call") {
      // Show API call animation for a short time
      setVisibleMessages((prev) => [...prev, currentMessage])
      setTimeout(() => {
        setMessageIndex((prev) => prev + 1)
      }, 2000)
    } else if (currentMessage.type === "code") {
      // Show code immediately
      setVisibleMessages((prev) => [...prev, currentMessage])
      setMessageIndex((prev) => prev + 1)
    } else {
      // For regular text messages, show typing animation
      setIsTyping(true)
      setTypingText("")
      setTypingIndex(0)

      // Add the message container but with empty content
      setVisibleMessages((prev) => [...prev, { ...currentMessage, content: "" }])

      // Start typing animation
      const textToType = currentMessage.content
      const typingInterval = setInterval(() => {
        setTypingIndex((prev) => {
          if (prev < textToType.length) {
            setTypingText(textToType.substring(0, prev + 1))
            return prev + 1
          } else {
            clearInterval(typingInterval)
            setIsTyping(false)
            // Update the message with full content
            setVisibleMessages((prev) =>
              prev.map((msg, idx) => (idx === prev.length - 1 ? { ...msg, content: textToType } : msg)),
            )
            // Move to next message after a delay
            setTimeout(() => {
              setMessageIndex((prevIndex) => prevIndex + 1)
            }, 1000)
            return prev
          }
        })
      }, 50) // Typing speed

      return () => clearInterval(typingInterval)
    }
  }, [messageIndex, currentExampleIndex])

  const currentExample = conversationExamples[currentExampleIndex]

  return (
    <div
      className="relative bg-card border rounded-xl shadow-xl p-4 h-full flex flex-col chat-container"
      style={{
        opacity: 1,
        transition: "opacity 0.5s ease-in-out",
      }}
      key={currentExampleIndex}
    >
      {/* Chat header */}
      <div className="flex items-center pb-3 border-b">
        <div className="h-8 w-8 rounded-full bg-primary/20 flex items-center justify-center">
          <Bot className="h-4 w-4 text-primary" />
        </div>
        <div className="ml-2 font-medium">AI Assistant</div>
        <div className="ml-auto text-xs text-muted-foreground">{currentExample.title}</div>
      </div>

      {/* Chat messages */}
      <div className="flex-1 py-3 overflow-hidden space-y-3">
        {visibleMessages.map((message, index) => {
          if (message.role === "user") {
            return (
              <div key={index} className="flex justify-end mb-3">
                <div className="bg-primary/10 text-sm rounded-lg py-2 px-3 max-w-[80%]">{message.content}</div>
              </div>
            )
          } else if (message.type === "api-call") {
            return (
              <div key={index} className="flex justify-center mb-3">
                <div className="bg-blue-50 dark:bg-blue-900/20 text-xs rounded-md py-1 px-2 border border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-300 flex items-center">
                  <div className="h-3 w-3 border-t-2 border-blue-500 border-r-2 rounded-full animate-spin mr-1"></div>
                  {message.apiCallType === "database" && <Database className="h-3 w-3 mr-1" />}
                  {message.apiCallType === "document" && <FileText className="h-3 w-3 mr-1" />}
                  {message.content}
                </div>
              </div>
            )
          } else if (message.type === "code") {
            return (
              <div key={index} className="flex items-start">
                <div className="h-6 w-6 rounded-full bg-primary/20 flex items-center justify-center mr-2">
                  <Bot className="h-3 w-3 text-primary" />
                </div>
                <div className="bg-muted text-sm rounded-lg py-2 px-3 max-w-[80%] font-mono whitespace-pre overflow-x-auto">
                  <div className="flex items-center mb-1">
                    <Code className="h-3 w-3 mr-1" />
                    <span className="text-xs text-muted-foreground">JavaScript</span>
                  </div>
                  {message.content}
                </div>
              </div>
            )
          } else {
            // Regular text message
            return (
              <div key={index} className="flex items-start">
                <div className="h-6 w-6 rounded-full bg-primary/20 flex items-center justify-center mr-2">
                  <Bot className="h-3 w-3 text-primary" />
                </div>
                <div className="bg-muted text-sm rounded-lg py-2 px-3 max-w-[80%] relative">
                  {index === visibleMessages.length - 1 && isTyping ? (
                    <span>
                      {typingText}
                      <span className="animate-pulse">|</span>
                    </span>
                  ) : (
                    <span>{message.content}</span>
                  )}
                  {!isTyping && index === visibleMessages.length - 1 && (
                    <span className="absolute right-2 bottom-1 text-xs text-muted-foreground">
                      <Check className="h-3 w-3 inline" />
                    </span>
                  )}
                </div>
              </div>
            )
          }
        })}
      </div>

      {/* Chat input */}
      <div className="border-t pt-3">
        <div className="relative">
          <div className="h-9 px-3 py-2 rounded-md border bg-background text-sm text-muted-foreground">
            Ask a question...
          </div>
          <button className="absolute right-2 top-1/2 -translate-y-1/2 h-5 w-5 rounded-full bg-primary flex items-center justify-center">
            <ArrowUp className="h-3 w-3 text-white" />
          </button>
        </div>
      </div>
    </div>
  )
}
