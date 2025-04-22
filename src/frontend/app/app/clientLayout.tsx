"use client"

import type React from "react"
import { usePathname } from "next/navigation"
import "./globals.css"
import { Inter } from "next/font/google"
import { ThemeProvider } from "@/components/theme-provider"
import Sidebar from "@/components/sidebar"
import Header from "@/components/header"
import { Toaster } from "@/components/ui/toaster"

const inter = Inter({ subsets: ["latin"] })

// This is a client component wrapper to access the pathname
function LayoutWithPathname({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const isSettingsPage = pathname?.startsWith("/settings")

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        {!isSettingsPage && <Sidebar />}
        <main className="flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  )
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
          <LayoutWithPathname>{children}</LayoutWithPathname>
          <Toaster />
        </ThemeProvider>
      </body>
    </html>
  )
}
