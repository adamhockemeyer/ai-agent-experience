"use client"

import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Bot, Code, FileText, Settings, MessageSquare, Zap, Database, Lock, ArrowRight } from "lucide-react"
import HeroChatShowcase from "@/components/hero-chat-showcase"

export default function Home() {
  return (
    <div className="flex flex-col min-h-full">
      {/* Hero Section */}
      <section className="bg-gradient-to-b from-primary/10 to-background py-16 px-4">
        <div className="container mx-auto max-w-5xl">
          <div className="flex flex-col md:flex-row items-center gap-8">
            <div className="flex-1 space-y-4">
              <h1 className="text-4xl md:text-5xl font-bold tracking-tight">
                Build Powerful AI Agents for Your Business
              </h1>
              <p className="text-xl text-muted-foreground">
                Create, configure, and deploy custom AI agents with powerful capabilities to solve your specific
                business challenges.
              </p>
              <div className="flex flex-wrap gap-4 pt-4">
                <Link href="/settings?tab=agents">
                  <Button size="lg" className="gap-2">
                    <Bot className="h-5 w-5" />
                    Create Your First Agent
                    <ArrowRight className="h-4 w-4 ml-1" />
                  </Button>
                </Link>
                <Link href="/settings">
                  <Button size="lg" variant="outline" className="gap-2">
                    <Settings className="h-5 w-5" />
                    Configure Platform
                  </Button>
                </Link>
              </div>
            </div>
            <div className="flex-1 flex justify-center">
              <div className="relative w-full max-w-md aspect-square">
                <div className="absolute inset-0 bg-primary/20 rounded-full blur-3xl opacity-50"></div>
                <HeroChatShowcase />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-16 px-4">
        <div className="container mx-auto max-w-5xl">
          <h2 className="text-3xl font-bold text-center mb-12">Powerful AI Capabilities</h2>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* Feature 1 */}
            <div className="bg-card border rounded-lg p-6 shadow-sm hover:shadow-md transition-shadow">
              <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center mb-4">
                <MessageSquare className="h-6 w-6 text-primary" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Natural Conversations</h3>
              <p className="text-muted-foreground">
                Engage in natural, context-aware conversations with AI agents trained on your specific domain.
              </p>
            </div>

            {/* Feature 2 */}
            <div className="bg-card border rounded-lg p-6 shadow-sm hover:shadow-md transition-shadow">
              <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center mb-4">
                <Code className="h-6 w-6 text-primary" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Code Interpreter</h3>
              <p className="text-muted-foreground">
                Execute code, analyze data, and generate visualizations directly within your conversations.
              </p>
            </div>

            {/* Feature 3 */}
            <div className="bg-card border rounded-lg p-6 shadow-sm hover:shadow-md transition-shadow">
              <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center mb-4">
                <FileText className="h-6 w-6 text-primary" />
              </div>
              <h3 className="text-xl font-semibold mb-2">File Processing</h3>
              <p className="text-muted-foreground">
                Upload and process documents, images, and data files for intelligent analysis and insights.
              </p>
            </div>

            {/* Feature 4 */}
            <div className="bg-card border rounded-lg p-6 shadow-sm hover:shadow-md transition-shadow">
              <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center mb-4">
                <Zap className="h-6 w-6 text-primary" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Custom Tools</h3>
              <p className="text-muted-foreground">
                Connect your agents to external APIs and services using OpenAPI specifications.
              </p>
            </div>

            {/* Feature 5 */}
            <div className="bg-card border rounded-lg p-6 shadow-sm hover:shadow-md transition-shadow">
              <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center mb-4">
                <Database className="h-6 w-6 text-primary" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Centralized Configuration</h3>
              <p className="text-muted-foreground">
                Manage all your agents and settings in one place with Azure App Configuration.
              </p>
            </div>

            {/* Feature 6 */}
            <div className="bg-card border rounded-lg p-6 shadow-sm hover:shadow-md transition-shadow">
              <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center mb-4">
                <Lock className="h-6 w-6 text-primary" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Enterprise Security</h3>
              <p className="text-muted-foreground">
                Secure your agents with Microsoft Entra ID authentication and role-based access control.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="bg-primary/5 py-16 px-4 mt-auto">
        <div className="container mx-auto max-w-5xl text-center">
          <h2 className="text-3xl font-bold mb-4">Ready to get started?</h2>
          <p className="text-xl text-muted-foreground mb-8 max-w-2xl mx-auto">
            Create your first AI agent and discover how it can transform your business processes.
          </p>
          <Link href="/settings?tab=agents">
            <Button size="lg" className="gap-2">
              <Bot className="h-5 w-5" />
              Create Your First Agent
              <ArrowRight className="h-4 w-4 ml-1" />
            </Button>
          </Link>
        </div>
      </section>
    </div>
  )
}
