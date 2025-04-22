"use client"

import { useState, useEffect } from "react"
import "highlight.js/styles/github-dark.css"

export default function MarkdownRenderer({ content }: { content: string }) {
  const [renderedContent, setRenderedContent] = useState("")
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const renderMarkdown = async () => {
      try {
        // Dynamically import marked to avoid SSR issues
        const { marked } = await import("marked")

        // Configure marked
        marked.setOptions({
          gfm: true, // GitHub Flavored Markdown
          breaks: true, // Convert \n to <br>
          headerIds: true,
          mangle: false,
          // Use a simpler highlight function that doesn't depend on highlight.js
          highlight: (code, lang) => {
            // Add a simple class to the code block
            if (lang) {
              // Apply some very basic syntax highlighting for Python
              if (lang === "python") {
                return (
                  code
                    // Keywords
                    .replace(
                      /\b(def|class|import|from|as|return|if|else|elif|for|while|try|except|finally|with|in|is|not|and|or|True|False|None)\b/g,
                      '<span class="keyword">$1</span>',
                    )
                    // Strings
                    .replace(/(["'])(.*?)\1/g, '<span class="string">$1$2$1</span>')
                    // Numbers
                    .replace(/\b(\d+)\b/g, '<span class="number">$1</span>')
                    // Comments
                    .replace(/(#.*)$/gm, '<span class="comment">$1</span>')
                )
              }
            }
            return code
          },
        })

        // Render the markdown
        const html = marked(content)
        setRenderedContent(html)
      } catch (error) {
        console.error("Error rendering markdown:", error)
        // Fallback to simple formatting
        setRenderedContent(simpleMarkdownFallback(content))
      } finally {
        setIsLoading(false)
      }
    }

    renderMarkdown()
  }, [content])

  // Simple fallback renderer for when the dynamic import fails
  function simpleMarkdownFallback(text: string): string {
    return text
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>") // Bold
      .replace(/\*(.*?)\*/g, "<em>$1</em>") // Italic
      .replace(
        /```([a-z]*)([\s\S]*?)```/g,
        '<pre class="bg-secondary/50 dark:bg-secondary/30 p-3 rounded-md overflow-x-auto my-2"><code>$2</code></pre>',
      ) // Code blocks
      .replace(/`([^`]+)`/g, '<code class="bg-secondary/50 dark:bg-secondary/30 px-1 py-0.5 rounded text-sm">$1</code>') // Inline code
      .replace(
        /\[([^\]]+)\]$$([^)]+)$$/g,
        '<a href="$2" class="text-primary hover:underline" target="_blank" rel="noopener noreferrer">$1</a>',
      ) // Links
      .replace(/\n\n/g, "<br><br>") // Line breaks
  }

  if (isLoading) {
    // Show the content with minimal formatting while loading
    return <div dangerouslySetInnerHTML={{ __html: simpleMarkdownFallback(content) }} />
  }

  return <div dangerouslySetInnerHTML={{ __html: renderedContent }} className="markdown-content" />
}
