"use client"

import { Component, type ErrorInfo, type ReactNode } from "react"

interface ErrorBoundaryProps {
  children: ReactNode
  fallback?: ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
}

export class AgentVisualizationErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError(_: Error): ErrorBoundaryState {
    return { hasError: true }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Error in agent visualization:", error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback || (
          <div className="mt-2 p-4 border rounded-md bg-muted/20">
            <h3 className="text-sm font-medium mb-2">Agent Visualization</h3>
            <div className="p-4 text-center text-muted-foreground">
              <p>Unable to display visualization.</p>
              <p className="text-xs mt-1">Please try refreshing the page.</p>
            </div>
          </div>
        )
      )
    }

    return this.props.children
  }
}
