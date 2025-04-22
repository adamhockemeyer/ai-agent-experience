"use client"

import { useState, useEffect } from "react"

export default function BotTypingIndicator() {
  const [dots, setDots] = useState(1)

  // Animate the dots
  useEffect(() => {
    const interval = setInterval(() => {
      setDots((prev) => (prev < 3 ? prev + 1 : 1))
    }, 500)

    return () => clearInterval(interval)
  }, [])

  return (
    <div className="flex items-center">
      <div className="flex items-center gap-1 bg-primary/10 px-4 py-2 rounded-full">
        <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
        <div className={`w-2 h-2 rounded-full bg-primary ${dots >= 2 ? "animate-pulse" : "opacity-30"}`} />
        <div className={`w-2 h-2 rounded-full bg-primary ${dots >= 3 ? "animate-pulse" : "opacity-30"}`} />
        <span className="ml-2 text-sm font-medium text-primary">
          {dots === 1 ? "Thinking" : dots === 2 ? "Thinking." : "Thinking.."}
        </span>
      </div>

      {/* Add a subtle pulsing glow effect */}
      <div
        className="absolute -inset-1 bg-primary/5 rounded-full blur-md animate-pulse-slow"
        style={{ animationDuration: "2s" }}
      />
    </div>
  )
}
