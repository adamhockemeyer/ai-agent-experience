import { getAgent } from "@/app/actions/agent-actions"
import AgentForm from "@/components/agent/agent-form"
import { notFound } from "next/navigation"

export default async function EditAgentPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  // Await the params promise to get the actual id
  const resolvedParams = await params

  // Don't try to fetch an agent if the ID is "new"
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
    <div className="container mx-auto py-10">
      <AgentForm agent={agent} isEditing />
    </div>
  )
}
