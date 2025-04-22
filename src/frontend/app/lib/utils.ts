import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatTimestamp(timestamp: number): string {
  return new Date(timestamp).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  })
}

export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text
  return text.slice(0, maxLength) + "..."
}

export function generateId(name: string): string {
  return name.toLowerCase().replace(/\s+/g, "_")
}

export function detectContentType(content: string): "text" | "code" | "image" | "iframe" {
  if (content.startsWith("<iframe")) {
    return "iframe"
  } else if (content.match(/^https?:\/\/.*\.(jpg|jpeg|png|gif|svg)/i)) {
    return "image"
  } else if (
    content.includes("```") ||
    content.includes("function") ||
    content.includes("class") ||
    content.includes("import")
  ) {
    return "code"
  } else {
    return "text"
  }
}

export function extractCodeLanguage(content: string): string | undefined {
  const match = content.match(/```([a-z]+)/i)
  return match ? match[1] : undefined
}

export function extractCodeContent(content: string): string {
  const match = content.match(/```(?:[a-z]+)?\n([\s\S]*?)\n```/i)
  return match ? match[1] : content
}
