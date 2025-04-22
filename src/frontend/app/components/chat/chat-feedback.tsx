"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { ThumbsUp, ThumbsDown, Bug, Copy } from "lucide-react"
import { submitFeedback } from "@/app/actions/agent-actions"
import { useToast } from "@/components/ui/use-toast"

interface ChatFeedbackProps {
  messageId: string
  traceId?: string
}

export default function ChatFeedback({ messageId, traceId }: ChatFeedbackProps) {
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [feedbackType, setFeedbackType] = useState<"positive" | "negative" | null>(null)
  const [comment, setComment] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const { toast } = useToast()

  const handleFeedback = async (type: "positive" | "negative") => {
    if (type === "positive") {
      // Submit positive feedback immediately without comment
      try {
        await submitFeedback({
          messageId,
          rating: "positive",
          traceId,
        })
        toast({
          title: "Feedback submitted",
          description: "Thank you for your feedback!",
        })
      } catch (error) {
        console.error("Error submitting feedback:", error)
        toast({
          title: "Error",
          description: "Failed to submit feedback. Please try again.",
          variant: "destructive",
        })
      }
    } else {
      // Open dialog for negative feedback to collect comment
      setFeedbackType("negative")
      setIsDialogOpen(true)
    }
  }

  const handleSubmitFeedback = async () => {
    if (!feedbackType) return

    setIsSubmitting(true)
    try {
      await submitFeedback({
        messageId,
        rating: feedbackType,
        comment: comment.trim() || undefined,
        traceId,
      })

      toast({
        title: "Feedback submitted",
        description: "Thank you for your feedback!",
      })

      setIsDialogOpen(false)
      setComment("")
    } catch (error) {
      console.error("Error submitting feedback:", error)
      toast({
        title: "Error",
        description: "Failed to submit feedback. Please try again.",
        variant: "destructive",
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleCopyToClipboard = () => {
    // This would copy the message content to clipboard
    toast({
      title: "Copied to clipboard",
      description: "The message has been copied to your clipboard.",
    })
  }

  const handleShowTraceId = () => {
    setFeedbackType(null)
    setIsDialogOpen(true)
  }

  return (
    <div className="flex items-center gap-2">
      <Button variant="ghost" size="sm" onClick={() => handleFeedback("positive")}>
        <ThumbsUp className="h-4 w-4 mr-1" />
        Helpful
      </Button>
      <Button variant="ghost" size="sm" onClick={() => handleFeedback("negative")}>
        <ThumbsDown className="h-4 w-4 mr-1" />
        Not Helpful
      </Button>
      <Button variant="ghost" size="sm" onClick={handleShowTraceId}>
        <Bug className="h-4 w-4 mr-1" />
        Debug
      </Button>
      <Button variant="ghost" size="sm" onClick={handleCopyToClipboard}>
        <Copy className="h-4 w-4 mr-1" />
        Copy
      </Button>

      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Debug Information</DialogTitle>
            <DialogDescription>Technical details for troubleshooting.</DialogDescription>
          </DialogHeader>

          {feedbackType === "negative" ? (
            <Textarea
              placeholder="Please provide details about what was wrong with the response..."
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              className="min-h-[100px]"
            />
          ) : (
            <div className="space-y-4">
              {traceId ? (
                <div className="bg-muted p-4 rounded-md">
                  <div className="text-sm font-medium mb-1">OpenTelemetry Trace ID:</div>
                  <div className="flex items-center">
                    <div className="font-mono text-xs bg-background p-2 rounded border overflow-x-auto flex-1">
                      {traceId}
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="ml-2"
                      onClick={() => {
                        navigator.clipboard.writeText(traceId)
                        toast({
                          title: "Copied",
                          description: "Trace ID has been copied to clipboard.",
                        })
                      }}
                    >
                      <Copy className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="text-muted-foreground text-sm">No trace ID available for this response.</div>
              )}

              <div className="bg-muted p-4 rounded-md">
                <div className="text-sm font-medium mb-1">Message Information:</div>
                <div className="text-xs">
                  <div>
                    <span className="font-medium">Message ID:</span> {messageId}
                  </div>
                </div>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button onClick={() => setIsDialogOpen(false)}>Close</Button>
            {feedbackType === "negative" && (
              <Button onClick={handleSubmitFeedback} disabled={isSubmitting}>
                {isSubmitting ? "Submitting..." : "Submit Feedback"}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
