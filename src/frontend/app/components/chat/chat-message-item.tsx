"use client"

import type { ChatMessage } from "@/lib/types"
import { User, Bot, ThumbsUp, ThumbsDown, Bug, Copy } from "lucide-react"
import { formatDistanceToNow } from "date-fns"
import { Button } from "@/components/ui/button"
import MarkdownRenderer from "./markdown-renderer"

interface ChatMessageItemProps {
  message: ChatMessage
}

export default function ChatMessageItem({ message }: ChatMessageItemProps) {
  const isUser = message.role === "user"

  return (
    <div className="flex items-start gap-3">
      <div
        className={`w-10 h-10 rounded-full flex items-center justify-center ${
          isUser ? "bg-secondary" : "bg-primary text-primary-foreground"
        }`}
      >
        {isUser ? <User className="h-5 w-5" /> : <Bot className="h-5 w-5" />}
      </div>
      <div className="flex-1">
        <div className={`p-3 rounded-lg overflow-hidden ${isUser ? "bg-secondary" : "bg-muted"}`}>
          <div className="markdown-content prose prose-sm dark:prose-invert max-w-none">
            <MarkdownRenderer content={message.content} />
          </div>

          {message.attachments && message.attachments.length > 0 && (
            <div className="mt-2 space-y-2">
              {message.attachments.map((attachment) => (
                <div key={attachment.id} className="flex items-center gap-2">
                  {attachment.type.startsWith("image/") ? (
                    <img
                      src={attachment.url || "/placeholder.svg"}
                      alt={attachment.name}
                      className="max-w-xs rounded-md"
                    />
                  ) : (
                    <div className="bg-background p-2 rounded-md text-sm">📎 {attachment.name}</div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Add feedback buttons inside the message for non-user messages */}
          {!isUser && (
            <div className="flex items-center justify-end gap-2 mt-2">
              <Button variant="ghost" size="sm">
                <ThumbsUp className="h-4 w-4 mr-1" />
                Helpful
              </Button>
              <Button variant="ghost" size="sm">
                <ThumbsDown className="h-4 w-4 mr-1" />
                Not Helpful
              </Button>
              <Button variant="ghost" size="sm">
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
        <div className="flex items-center justify-between mt-1">
          <div className="text-xs text-muted-foreground">
            {formatDistanceToNow(message.timestamp, { addSuffix: true })}
          </div>
        </div>
      </div>
    </div>
  )
}
