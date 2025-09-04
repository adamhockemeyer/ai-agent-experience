"use client"

import { FormField, FormItem, FormLabel, FormControl, FormDescription } from "@/components/ui/form"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Switch } from "@/components/ui/switch"
import { Input } from "@/components/ui/input"
import { Bot } from "lucide-react"
import { useEffect } from "react"
import type { UseFormReturn } from "react-hook-form"
import type { AgentFormValues } from "../utils/form-utils"

interface AdvancedSettingsSectionProps {
  form: UseFormReturn<AgentFormValues>
}

export default function AdvancedSettingsSection({ form }: AdvancedSettingsSectionProps) {
  const enableHistoryReduction = form.watch("enableHistoryReduction")
  const agentType = form.watch("agentType")
  const isChatCompletionAgent = agentType === "ChatCompletionAgent"

  // Reset enableHistoryReduction when agent type is not ChatCompletionAgent
  useEffect(() => {
    if (!isChatCompletionAgent && enableHistoryReduction) {
      form.setValue("enableHistoryReduction", false)
    }
  }, [isChatCompletionAgent, enableHistoryReduction, form])

  return (
    <Card className="border-gray-200 dark:border-gray-800">
      <CardHeader className="bg-gray-50 dark:bg-gray-900/50 rounded-t-lg">
        <CardTitle className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-gray-600 dark:text-gray-400" />
          Advanced Settings
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-6 space-y-4">
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

        <FormField
          control={form.control}
          name="enableHistoryReduction"
          render={({ field }) => (
            <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4 bg-gray-50/50 dark:bg-gray-900/20">
              <div className="space-y-0.5">
                <FormLabel className="text-base">Enable Chat History Reduction</FormLabel>
                <FormDescription>
                  {isChatCompletionAgent
                    ? "Automatically summarize and reduce chat history to manage long conversations efficiently."
                    : "Chat history reduction is only available for Chat Completion Agents."
                  }
                </FormDescription>
              </div>
              <FormControl>
                <Switch
                  checked={field.value}
                  onCheckedChange={field.onChange}
                  disabled={!isChatCompletionAgent}
                />
              </FormControl>
            </FormItem>
          )}
        />

        {enableHistoryReduction && isChatCompletionAgent && (
          <div className="grid grid-cols-2 gap-4 p-4 bg-blue-50/50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
            <FormField
              control={form.control}
              name="reducerMsgCount"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Message Count</FormLabel>
                  <FormControl>
                    <Input
                      type="number"
                      placeholder="10"
                      {...field}
                      onChange={(e) => field.onChange(parseInt(e.target.value) || 10)}
                    />
                  </FormControl>
                  <FormDescription>Target number of messages to retain after reduction</FormDescription>
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="reducerThreshold"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Threshold</FormLabel>
                  <FormControl>
                    <Input
                      type="number"
                      placeholder="10"
                      {...field}
                      onChange={(e) => field.onChange(parseInt(e.target.value) || 10)}
                    />
                  </FormControl>
                  <FormDescription>Buffer to prevent premature reduction</FormDescription>
                </FormItem>
              )}
            />
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export { AdvancedSettingsSection }
