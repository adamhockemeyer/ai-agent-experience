import type React from "react"
import "./globals.css"
import { Inter } from "next/font/google"
import { ThemeProvider } from "@/components/theme-provider"
import Header from "@/components/header"
import LayoutWithPathname from "@/components/layout-with-pathname"
import { Toaster } from "@/components/ui/toaster"

const inter = Inter({ subsets: ["latin"] })

export const metadata = {
  title: "AI Agents Showcase",
  description: "Showcase AI capabilities with configurable agents",
    generator: 'v0.dev'
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.className} antialiased`}>
        <ThemeProvider attribute="class" defaultTheme="light" enableSystem disableTransitionOnChange>
          <div className="flex flex-col h-screen overflow-hidden">
            <Header />
            <LayoutWithPathname>{children}</LayoutWithPathname>
          </div>
          <Toaster />
        </ThemeProvider>
      </body>
    </html>
  )
}
