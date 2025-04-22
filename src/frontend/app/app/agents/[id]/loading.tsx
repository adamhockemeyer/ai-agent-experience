import { Skeleton } from "@/components/ui/skeleton"
import { Bot } from "lucide-react"

export default function AgentLoading() {
  return (
    <div className="flex flex-col h-full">
      <div className="bg-gradient-to-r from-primary/5 to-background p-6 border-b">
        <div className="max-w-screen-xl mx-auto">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center text-primary animate-pulse">
                <Bot className="h-6 w-6 opacity-50" />
              </div>
              <div className="space-y-2">
                <Skeleton className="h-8 w-64" />
                <Skeleton className="h-4 w-96" />
                <div className="flex flex-wrap gap-2 mt-3">
                  <Skeleton className="h-6 w-32 rounded-full" />
                  <Skeleton className="h-6 w-40 rounded-full" />
                  <Skeleton className="h-6 w-36 rounded-full" />
                </div>
              </div>
            </div>
            <Skeleton className="h-9 w-28" />
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-hidden flex items-center justify-center">
        <div className="text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-primary/10 mb-4">
            <div className="h-8 w-8 border-4 border-primary/30 border-t-primary rounded-full animate-spin"></div>
          </div>
          <h3 className="text-xl font-medium mb-2">Loading Agent</h3>
          <p className="text-muted-foreground">Fetching agent configuration and capabilities...</p>
        </div>
      </div>
    </div>
  )
}
