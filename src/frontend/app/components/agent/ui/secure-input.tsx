"use client"

import React, { useState } from "react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"

interface SecureInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  value: string
  onChange: (value: string) => void
}

const SecureInput = React.memo(function SecureInput({ value, onChange, ...props }: SecureInputProps) {
  // Use a local state to track if we're showing the actual value or not
  const [isRevealed, setIsRevealed] = useState(false)

  // Handle changes to the input
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange(e.target.value)
  }

  // Use a stable layout that won't trigger unnecessary resize events
  return (
    <div className="relative">
      <Input
        type={isRevealed ? "text" : "password"}
        value={value}
        onChange={handleChange}
        className="pr-20"
        {...props}
      />
      <div className="absolute inset-y-0 right-0 flex items-center pr-3">
        {value && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-5 px-1 text-xs text-muted-foreground hover:text-foreground"
            onClick={() => setIsRevealed(!isRevealed)}
          >
            {isRevealed ? "Hide" : "Show"}
          </Button>
        )}
      </div>
    </div>
  )
})

export default SecureInput
