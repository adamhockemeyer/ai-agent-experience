"use client"

import { useState, useEffect } from "react"
//import "highlight.js/styles/github-dark.css"
import hljs from "highlight.js"

export default function MarkdownRenderer({ content }: { content: string }) {
  const [renderedContent, setRenderedContent] = useState("")
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const renderMarkdown = async () => {
      try {
        // Dynamically import marked and marked-highlight to avoid SSR issues
        const { marked } = await import("marked")
        const { markedHighlight } = await import("marked-highlight")

        // Configure marked with marked-highlight
        marked.use(
          markedHighlight({
            langPrefix: "hljs language-",
            highlight(code, lang) {
              // Skip if code appears to be already highlighted (contains hljs spans)
              if (code.includes('class="hljs')) {
                return code
              }

              // Skip if code contains our iframe marker to prevent double processing
              if (code.includes('data-iframe-html')) {
                return code
              }

              console.log("Highlighting code with language:", lang)

              // Check if language is HTML - if so, we'll render it as an iframe
              if (lang && lang.toLowerCase() === "html") {
                console.log("Detected HTML content, will render as iframe")
                // We'll process this HTML content in the renderer
                return `<div data-iframe-html>${encodeURIComponent(code)}</div>`
              }

              if (lang && hljs.getLanguage(lang)) {
                try {
                  return hljs.highlight(code, { language: lang }).value
                } catch (err) {
                  console.error("Error highlighting code:", err)
                }
              }
              return code // Return original code if language is not supported
            },
          })
        )

        // Configure marked options
        marked.setOptions({
          gfm: true, // GitHub Flavored Markdown
          breaks: true, // Convert \n to <br>
        })


        console.log("Rendering markdown content:", content)


        // Render the markdown and ensure we get a string
        const html = await marked.parse(content)

        // Process any HTML iframes
        const processedHtml = processHtmlIframes(html)
        setRenderedContent(processedHtml)
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

  // Process HTML content marked for iframe rendering
  function processHtmlIframes(html: string): string {
    // Use non-greedy match with RegExp to ensure we don't match nested patterns
    // Also use a regex that won't match if it's already been processed
    const regex = /<div data-iframe-html>([^<]*)<\/div>/g;

    return html.replace(regex, (_, encodedHtml) => {
      try {
        // Prevent double-decoding by checking if it looks like encoded content
        if (!encodedHtml.includes('%')) {
          console.log("Content doesn't appear to be encoded, using as is");
          return encodedHtml;
        }

        const decodedHtml = decodeURIComponent(encodedHtml)

        // Safety check - if the decoded HTML still contains our marker, it might be recursion
        if (decodedHtml.includes('data-iframe-html')) {
          console.error("Detected potential recursion in HTML iframe processing");
          return `<div class="text-red-500">Error: Detected recursion in HTML processing</div>`;
        }

        // Create a sandboxed iframe containing the HTML with responsive sizing
        return `
          <div class="html-preview mb-4">
            <div class="relative w-full" style="aspect-ratio: 16/9; min-height: 200px; max-height: 70vh;">
              <iframe
                srcDoc="${decodedHtml.replace(/"/g, '&quot;')}"
                sandbox="allow-scripts allow-same-origin"
                class="w-full h-full border-0 rounded-md bg-white"
                loading="lazy"
                title="HTML Preview"
              ></iframe>
            </div>
          </div>
        `
      } catch (e) {
        console.error("Error processing HTML iframe:", e)
        return `<div class="text-red-500">Error rendering HTML content</div>`
      }
    })
  }

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
        /\[([^\]]+)\]\(([^)]+)\)/g,
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