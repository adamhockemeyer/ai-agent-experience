"use client"

import { FormField, FormItem, FormLabel, FormControl, FormDescription } from "@/components/ui/form"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Switch } from "@/components/ui/switch"
import { Bot } from "lucide-react"
import type { UseFormReturn } from "react-hook-form"
import type { AgentFormValues } from "../utils/form-utils"

interface AdvancedSettingsSectionProps {
  form: UseFormReturn<AgentFormValues>
}

export default function AdvancedSettingsSection({ form }: AdvancedSettingsSectionProps) {
  return (
    <Card className="border-gray-200 dark:border-gray-800">
      <CardHeader className="bg-gray-50 dark:bg-gray-900/50 rounded-t-lg">
        <CardTitle className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-gray-600 dark:text-gray-400" />
          Advanced Settings
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-6">
        <FormField
          control={form.control}
          name="requireJsonResponse"
          render={({ field }) => (
            <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4 bg-gray-50/50 dark:bg-gray-900/20">
              <div className="space-y-0.5">
                <FormLabel className="text-base">Require JSON Response</FormLabel>
                <FormDescription>Require the agent to respond with JSON when making tool calls.</FormDescription>
              </div>
              <FormControl>
                <Switch checked={field.value} onCheckedChange={field.onChange} />
              </FormControl>
            </FormItem>
          )}
        />
      </CardContent>
    </Card>
  )
}

export { AdvancedSettingsSection }
