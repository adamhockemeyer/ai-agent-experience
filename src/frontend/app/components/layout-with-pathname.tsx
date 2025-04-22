"use client"

import type React from "react"

import { usePathname } from "next/navigation"
import Sidebar from "@/components/sidebar"

export default function LayoutWithPathname({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const isSettingsPage = pathname?.startsWith("/settings")
  const isAgentEditPage = pathname?.includes("/agents/new") || pathname?.includes("/edit")
  const shouldHideSidebar = isSettingsPage || isAgentEditPage

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <div className="flex flex-1 overflow-hidden">
        {!shouldHideSidebar && <Sidebar />}
        <main className="flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  )
}
