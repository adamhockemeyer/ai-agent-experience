import { getAgent } from "@/app/actions/agent-actions"
import ChatInterface from "@/components/chat/chat-interface"
import { notFound } from "next/navigation"
import { Bot, Code, FileText, Settings, Zap, Cpu, Workflow } from "lucide-react"
import { Button } from "@/components/ui/button"
import Link from "next/link"
import AgentForm from "@/components/agent/agent-form"


export default async function AgentPage({ params }: {
  params: Promise<{ id: string }>
}) {

  // Await the params promise to get the actual id
  const resolvedParams = await params

  // Special case for "new" - render the agent form directly
  if (resolvedParams.id === "new") {
    return (
      <div className="container mx-auto py-10">
        <AgentForm />
      </div>
    )
  }

  const agent = await getAgent(resolvedParams.id)

  if (!agent) {
    notFound()
  }

  return (
    <div className="flex flex-col h-full">
      <div className="bg-gradient-to-r from-primary/5 to-background p-6 border-b">
        <div className="max-w-screen-xl mx-auto">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center text-primary">
                {agent.tools && agent.tools.some((tool) => tool.type === "Agent") ? (
                  <Workflow className="h-6 w-6" />
                ) : (
                  <Bot className="h-6 w-6" />
                )}
              </div>
              <div>
                <h2 className="text-2xl font-bold">{agent.name}</h2>
                <p className="text-muted-foreground mt-1 max-w-2xl">{agent.description}</p>

                <div className="flex flex-wrap items-center gap-2 mt-3">
                  <div className="bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-300 px-3 py-1 rounded-full text-sm flex items-center">
                    <Cpu className="h-3.5 w-3.5 mr-1.5" />
                    {agent.agentType === "AzureAIAgent" ? "Azure AI Agent" : "Chat Completion Agent"}
                  </div>

                  <div className="bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300 px-3 py-1 rounded-full text-sm flex items-center">
                    <Bot className="h-3.5 w-3.5 mr-1.5" />
                    {agent.modelSelection.provider}: {agent.modelSelection.model}
                  </div>

                  {agent.codeInterpreter && (
                    <div className="bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300 px-3 py-1 rounded-full text-sm flex items-center">
                      <Code className="h-3.5 w-3.5 mr-1.5" />
                      Code Interpreter
                    </div>
                  )}

                  {agent.fileUpload && (
                    <div className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300 px-3 py-1 rounded-full text-sm flex items-center">
                      <FileText className="h-3.5 w-3.5 mr-1.5" />
                      File Upload
                    </div>
                  )}

                  {agent.tools.length > 0 && (
                    <div className="bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300 px-3 py-1 rounded-full text-sm flex items-center">
                      <Zap className="h-3.5 w-3.5 mr-1.5" />
                      {agent.tools.length} {agent.tools.length === 1 ? "Tool" : "Tools"}
                    </div>
                  )}
                </div>
              </div>
            </div>

            <Link href={`/agents/${resolvedParams.id}/edit`}>
              <Button variant="outline" size="sm" className="shadow-sm">
                <Settings className="h-4 w-4 mr-2" />
                Configure
              </Button>
            </Link>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-hidden">
        <ChatInterface agent={agent} />
      </div>
    </div>
  )
}
